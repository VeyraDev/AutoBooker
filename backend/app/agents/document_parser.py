"""Parse PDF/DOCX/TXT, classify 资料 vs 参考文献；参考文献分块 embedding 入库。"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.llm.client import LLMClient
from app.models.book import Book
from app.models.reference import ParseStatus, ReferenceChunk, ReferenceFile

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_MATERIAL_NAME_KW = ("要求", "约束", "风格", "说明", "不要", "注意", "术语")
_ACADEMIC_TEXT_KW = (
    "Abstract",
    "摘要",
    "关键词",
    "Keywords",
    "参考文献",
    "DOI",
    "Introduction",
    "Conclusion",
)


class DocumentParserAgent:
    def __init__(self, db: Session, book_id: uuid.UUID) -> None:
        self.db = db
        self.book_id = book_id
        self._client = LLMClient()

    @staticmethod
    def extract_text(file_path: str, file_type: str) -> str:
        ft = file_type.lower()
        if ft == "txt":
            return Path(file_path).read_text(encoding="utf-8", errors="replace")
        if ft == "pdf":
            doc = fitz.open(file_path)
            try:
                return "\n".join(page.get_text() for page in doc)
            finally:
                doc.close()
        if ft == "docx":
            doc = DocxDocument(file_path)
            return "\n".join(p.text for p in doc.paragraphs if p.text and p.text.strip())
        raise ValueError(f"Unsupported file type: {file_type}")

    @staticmethod
    def classify_file(text: str, filename: str) -> str:
        """返回 material（资料型全文注入）或 reference（RAG）。"""
        word_count = len(text)
        lower_name = filename.lower()

        if any(kw in text for kw in _ACADEMIC_TEXT_KW):
            return "reference"
        if word_count < 5000 and any(kw in filename for kw in _MATERIAL_NAME_KW):
            return "material"
        if word_count < 5000:
            return "material"
        return "reference"

    @staticmethod
    def chunk_text(text: str) -> list[str]:
        if not text.strip():
            return []
        chunks: list[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(start + CHUNK_SIZE, n)
            chunks.append(text[start:end])
            if end >= n:
                break
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    def _store_as_material(self, text: str, ref: ReferenceFile) -> None:
        book = self.db.get(Book, self.book_id)
        if not book:
            raise RuntimeError("book not found for material ingest")
        snippet = text[:5000]
        existing = (book.user_material or "").strip()
        if existing:
            book.user_material = existing + "\n\n---\n\n" + snippet
        else:
            book.user_material = snippet
        ref.ingest_kind = "material"
        from datetime import datetime, timezone

        ref.parse_status = ParseStatus.done
        ref.error_message = None
        ref.parsed_at = datetime.now(timezone.utc)
        self.db.commit()

    def _embed_and_store_chunks(self, file_id: uuid.UUID, chunks: list[str]) -> None:
        embeddings: list[list[float]] = []
        batch_size = min(settings.EMBEDDING_BATCH_SIZE, 25)
        for i in range(0, len(chunks), batch_size):
            embeddings.extend(self._client.embed(chunks[i : i + batch_size]))

        if len(embeddings) != len(chunks):
            raise RuntimeError("embedding count mismatch")

        self.db.query(ReferenceChunk).filter(ReferenceChunk.file_id == file_id).delete()

        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            self.db.add(
                ReferenceChunk(
                    book_id=self.book_id,
                    file_id=file_id,
                    chunk_index=idx,
                    content=chunk,
                    embedding=emb,
                )
            )

    def parse_and_store(
        self,
        file_id: uuid.UUID,
        file_path: str,
        file_type: str,
        *,
        forced_class: str | None = None,
    ) -> None:
        ref = self.db.get(ReferenceFile, file_id)
        if not ref or ref.book_id != self.book_id:
            logger.error("ReferenceFile %s not found for book %s", file_id, self.book_id)
            return

        ref.parse_status = ParseStatus.processing
        ref.error_message = None
        ref.ingest_kind = "reference"
        self.db.commit()

        try:
            text = self.extract_text(file_path, file_type)
            if forced_class in ("material", "reference"):
                file_class = forced_class
            else:
                file_class = self.classify_file(text, ref.filename or "")

            if file_class == "material":
                self._store_as_material(text, ref)
                return

            ref.ingest_kind = "reference"
            chunks = self.chunk_text(text)
            if not chunks:
                ref.parse_status = ParseStatus.done
                ref.error_message = "No text extracted"
                from datetime import datetime, timezone

                ref.parsed_at = datetime.now(timezone.utc)
                self.db.commit()
                return

            self._embed_and_store_chunks(file_id, chunks)

            from datetime import datetime, timezone

            ref.parse_status = ParseStatus.done
            ref.parsed_at = datetime.now(timezone.utc)
            self.db.commit()

            self._try_extract_bibliography_citations(text, file_id)
        except Exception as e:
            logger.exception("parse_and_store failed: %s", e)
            ref.parse_status = ParseStatus.failed
            ref.error_message = str(e)[:2000]
            self.db.commit()

    def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        any_chunk = self.db.execute(
            select(ReferenceChunk.id).where(ReferenceChunk.book_id == self.book_id).limit(1)
        ).first()
        if not any_chunk:
            return []
        try:
            qvec = self._client.embed([query])[0]
        except Exception as e:
            logger.warning("embedding unavailable for RAG retrieve; skipping snippets: %s", e)
            return []
        stmt = (
            select(ReferenceChunk)
            .where(ReferenceChunk.book_id == self.book_id)
            .order_by(ReferenceChunk.embedding.cosine_distance(qvec))
            .limit(top_k)
        )
        rows = self.db.execute(stmt).scalars().all()
        return [r.content for r in rows]

    def retrieve_with_meta(self, query: str, top_k: int = 5) -> tuple[list[str], list[tuple[str, str]]]:
        """Returns (snippets, [(content, filename), ...])."""
        any_chunk = self.db.execute(
            select(ReferenceChunk.id).where(ReferenceChunk.book_id == self.book_id).limit(1)
        ).first()
        if not any_chunk:
            return [], []
        try:
            qvec = self._client.embed([query])[0]
        except Exception as e:
            logger.warning("embedding unavailable for RAG retrieve_with_meta; skipping snippets: %s", e)
            return [], []
        stmt = (
            select(ReferenceChunk, ReferenceFile.filename)
            .join(ReferenceFile, ReferenceChunk.file_id == ReferenceFile.id)
            .where(ReferenceChunk.book_id == self.book_id)
            .order_by(ReferenceChunk.embedding.cosine_distance(qvec))
            .limit(top_k)
        )
        rows = self.db.execute(stmt).all()
        snippets: list[str] = []
        pairs: list[tuple[str, str]] = []
        for chunk_row, filename in rows:
            snippets.append(chunk_row.content)
            pairs.append((chunk_row.content, filename or ""))
        return snippets, pairs

    def _try_extract_bibliography_citations(self, text: str, file_id: uuid.UUID) -> None:
        """从参考文献型上传文件中解析书末条目并写入 citations 表。"""
        try:
            from app.agents.literature_agent import lookup_crossref_by_doi
            from app.models.book import Book
            from app.services.citation_service import ingest_uploaded_bibliography

            book = self.db.get(Book, self.book_id)
            if not book:
                return
            n = ingest_uploaded_bibliography(
                self.db,
                book,
                text,
                file_id,
                lookup_doi=lookup_crossref_by_doi,
            )
            if n:
                logger.info("extracted %s bibliography citations for book %s", n, self.book_id)
        except Exception as e:
            logger.warning("bibliography extraction skipped: %s", e)
