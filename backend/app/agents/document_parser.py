"""Parse PDF/DOCX, chunk, embed, store in pgvector; retrieve for RAG."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.llm.client import LLMClient
from app.models.reference import ParseStatus, ReferenceChunk, ReferenceFile

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


class DocumentParserAgent:
    def __init__(self, db: Session, book_id: uuid.UUID) -> None:
        self.db = db
        self.book_id = book_id
        self._client = LLMClient()

    @staticmethod
    def extract_text(file_path: str, file_type: str) -> str:
        ft = file_type.lower()
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

    def parse_and_store(self, file_id: uuid.UUID, file_path: str, file_type: str) -> None:
        ref = self.db.get(ReferenceFile, file_id)
        if not ref or ref.book_id != self.book_id:
            logger.error("ReferenceFile %s not found for book %s", file_id, self.book_id)
            return

        ref.parse_status = ParseStatus.processing
        ref.error_message = None
        self.db.commit()

        try:
            text = self.extract_text(file_path, file_type)
            chunks = self.chunk_text(text)
            if not chunks:
                ref.parse_status = ParseStatus.done
                ref.error_message = "No text extracted"
                from datetime import datetime, timezone

                ref.parsed_at = datetime.now(timezone.utc)
                self.db.commit()
                return

            embeddings: list[list[float]] = []
            batch_size = min(settings.EMBEDDING_BATCH_SIZE, 25)
            for i in range(0, len(chunks), batch_size):
                embeddings.extend(self._client.embed(chunks[i : i + batch_size]))

            if len(embeddings) != len(chunks):
                raise RuntimeError("embedding count mismatch")

            # Replace existing chunks for this file if re-parse
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

            from datetime import datetime, timezone

            ref.parse_status = ParseStatus.done
            ref.parsed_at = datetime.now(timezone.utc)
            self.db.commit()
        except Exception as e:
            logger.exception("parse_and_store failed: %s", e)
            ref.parse_status = ParseStatus.failed
            ref.error_message = str(e)[:2000]
            self.db.commit()

    def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        qvec = self._client.embed([query])[0]
        stmt = (
            select(ReferenceChunk)
            .where(ReferenceChunk.book_id == self.book_id)
            .order_by(ReferenceChunk.embedding.cosine_distance(qvec))
            .limit(top_k)
        )
        rows = self.db.execute(stmt).scalars().all()
        return [r.content for r in rows]
