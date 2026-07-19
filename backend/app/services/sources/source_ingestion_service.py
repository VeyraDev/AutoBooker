"""Canonical full-text ingestion shared by assistant and reference uploads."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.document_parser import DocumentParserAgent
from app.database import SessionLocal
from app.models.book import Book
from app.models.intake import IntakeItem, IntakeItemStatus
from app.models.reference import (
    FileLifecycleStatus,
    FilePurpose,
    ParseStatus,
    ReferenceChunk,
    ReferenceFile,
    ReferenceFilePurpose,
)

logger = logging.getLogger(__name__)

SUPPORTED_FILE_TYPES = {"pdf", "docx", "txt", "md"}


def normalized_file_type(filename: str) -> str | None:
    file_type = Path(filename or "").suffix.lower().lstrip(".")
    if file_type not in SUPPORTED_FILE_TYPES:
        return None
    return "txt" if file_type == "md" else file_type


def build_role_scan_text(chunks: list[ReferenceChunk], *, max_chunks: int = 16) -> str:
    """Sample the whole document evenly so mixed roles are not inferred from the opening only."""
    if not chunks:
        return ""
    count = min(max(1, max_chunks), len(chunks))
    if count == 1:
        selected = [chunks[0]]
    else:
        indexes = {
            round(position * (len(chunks) - 1) / (count - 1))
            for position in range(count)
        }
        selected = [chunks[index] for index in sorted(indexes)]
    blocks: list[str] = []
    for chunk in selected:
        locator: list[str] = []
        if chunk.page_number:
            locator.append(f"第{chunk.page_number}页")
        headings = chunk.heading_path if isinstance(chunk.heading_path, list) else []
        if headings:
            locator.append(" > ".join(str(value) for value in headings if str(value).strip()))
        if chunk.paragraph_index:
            locator.append(f"第{chunk.paragraph_index}段")
        location = " · ".join(locator) or f"分块 {chunk.chunk_index + 1}"
        blocks.append(f"【位置：{location}】\n{chunk.content}")
    return "\n\n".join(blocks)


class SourceIngestionService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_full_text_index(self, book: Book, item: IntakeItem) -> ReferenceFile | None:
        """Create a ReferenceFile over the upload's existing binary asset."""
        file_type = normalized_file_type(item.filename or "")
        if not file_type or not item.asset_id:
            return None
        if item.reference_file_id:
            existing = self.db.get(ReferenceFile, item.reference_file_id)
            if existing and existing.book_id == book.id:
                return existing

        ref = ReferenceFile(
            book_id=book.id,
            filename=item.filename or "upload",
            asset_id=item.asset_id,
            storage_path=f"db://binary_assets/{item.asset_id}",
            file_type=file_type,
            ingest_kind="reference",
            parse_status=ParseStatus.pending,
            file_purposes=[FilePurpose.reference_material.value],
            lifecycle_status=FileLifecycleStatus.processing,
        )
        self.db.add(ref)
        self.db.flush()
        self.db.add(
            ReferenceFilePurpose(
                file_id=ref.id,
                purpose=FilePurpose.reference_material,
                confidence=100,
                user_confirmed=True,
                active=True,
            )
        )
        item.reference_file_id = ref.id
        self.db.flush()
        return ref


def run_source_index_task(book_id: UUID, source_id: UUID, reference_file_id: UUID) -> None:
    """Background entrypoint; status is mirrored back to the assistant source."""
    db = SessionLocal()
    try:
        item = db.get(IntakeItem, source_id)
        ref = db.get(ReferenceFile, reference_file_id)
        if not item or not ref or ref.book_id != book_id or ref.asset_id is None:
            return
        DocumentParserAgent(db, book_id).parse_from_asset(
            ref.id,
            ref.asset_id,
            ref.file_type,
            forced_class="reference",
        )
        db.refresh(ref)
        if ref.parse_status == ParseStatus.done:
            all_chunks = (
                db.query(ReferenceChunk)
                .filter(
                    ReferenceChunk.file_id == ref.id,
                    ReferenceChunk.chunk_kind == "reference_material",
                    ReferenceChunk.active.is_(True),
                )
                .order_by(ReferenceChunk.chunk_index.asc())
                .limit(500)
                .all()
            )
            first_chunks = all_chunks[:6]
            preview = "\n".join(row.content for row in first_chunks).strip()
            if preview:
                item.text_content = preview[:8000]
                item.parsed_preview = preview[:4000]
            item.status = IntakeItemStatus.parsed
            role_scan_text = build_role_scan_text(all_chunks)
            book = db.get(Book, book_id)
            if book and role_scan_text:
                from app.services.sources.source_segment_service import SourceSegmentService

                SourceSegmentService(db).extract_segments(
                    book,
                    item,
                    force=True,
                    text_override=role_scan_text,
                )
        else:
            item.status = IntakeItemStatus.failed
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("assistant source indexing failed book=%s source=%s", book_id, source_id)
        try:
            item = db.get(IntakeItem, source_id)
            if item:
                item.status = IntakeItemStatus.failed
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
