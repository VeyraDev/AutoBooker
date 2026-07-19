"""Unified source library over intake items."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.document_parser import DocumentParserAgent
from app.llm.client import LLMClient
from app.models.book import Book, CreationOrigin
from app.models.intake import IntakeItem, IntakeItemStatus, IntakeItemType, IntakeStatus, ProjectIntake
from app.models.generation_context_snapshot import GenerationContextSnapshot
from app.models.reference import FileLifecycleStatus, ParseStatus, ReferenceChunk, ReferenceFile
from app.services.intake.intake_services import IntakeItemService
from app.services.sources.source_segment_service import SourceSegmentService
from app.utils.json_llm import parse_llm_json


def _file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext or "bin"


def _source_status(item: IntakeItem, reference_file: ReferenceFile | None = None) -> str:
    if reference_file is not None:
        if reference_file.parse_status == ParseStatus.failed or reference_file.lifecycle_status == FileLifecycleStatus.failed:
            return "failed"
        if reference_file.parse_status in {ParseStatus.pending, ParseStatus.processing}:
            return "reading"
        if reference_file.lifecycle_status == FileLifecycleStatus.pending_confirmation:
            return "needs_confirm"
        if reference_file.parse_status == ParseStatus.done and reference_file.lifecycle_status == FileLifecycleStatus.effective:
            return "indexed"
    if item.status == IntakeItemStatus.failed:
        return "failed"
    if item.status == IntakeItemStatus.pending:
        return "reading"
    preview = (item.parsed_preview or item.text_content or "").strip()
    if preview and preview != "[上传文件，暂未提取到可用于意图识别的正文]":
        return "read"
    if item.item_type == IntakeItemType.upload:
        return "needs_confirm"
    return "read"


def _source_title(item: IntakeItem) -> str:
    if item.filename:
        return item.filename
    text = (item.text_content or "").strip()
    if not text:
        return "未命名资料"
    return text[:40] + ("…" if len(text) > 40 else "")


def _source_type(item: IntakeItem) -> str:
    if getattr(item, "source_type", None):
        return item.source_type
    if item.item_type == IntakeItemType.upload:
        return "upload"
    if item.item_type == IntakeItemType.pasted_text:
        return "pasted_text"
    return "natural_text"


class SourceLibraryService:
    def __init__(self, db: Session):
        self.db = db
        self._intake_items = IntakeItemService(db)

    def _ensure_intake(self, book: Book) -> ProjectIntake:
        origin = book.creation_origin or CreationOrigin.idea_only
        if not book.creation_origin:
            book.creation_origin = origin
        return self._intake_items.get_or_create_intake(book, origin)

    def ensure_missing_upload_indexes(self, book: Book) -> list[tuple[IntakeItem, ReferenceFile]]:
        """Lazily migrate uploads created before the canonical index link existed."""
        intake = (
            self.db.query(ProjectIntake)
            .filter(
                ProjectIntake.book_id == book.id,
                ProjectIntake.status != IntakeStatus.superseded,
            )
            .order_by(ProjectIntake.created_at.desc())
            .first()
        )
        if not intake:
            return []
        items = (
            self.db.query(IntakeItem)
            .filter(
                IntakeItem.intake_id == intake.id,
                IntakeItem.item_type == IntakeItemType.upload,
                IntakeItem.asset_id.isnot(None),
                IntakeItem.reference_file_id.is_(None),
                IntakeItem.status != IntakeItemStatus.disabled,
            )
            .all()
        )
        from app.services.sources.source_ingestion_service import SourceIngestionService

        ingestion = SourceIngestionService(self.db)
        queued: list[tuple[IntakeItem, ReferenceFile]] = []
        for item in items:
            ref = ingestion.ensure_full_text_index(book, item)
            if ref:
                queued.append((item, ref))
        return queued

    def list_sources(self, book: Book) -> list[dict]:
        intake = (
            self.db.query(ProjectIntake)
            .filter(
                ProjectIntake.book_id == book.id,
                ProjectIntake.status != IntakeStatus.superseded,
            )
            .order_by(ProjectIntake.created_at.desc())
            .first()
        )
        if not intake:
            return []
        items = (
            self.db.query(IntakeItem)
            .filter(IntakeItem.intake_id == intake.id, IntakeItem.status != IntakeItemStatus.disabled)
            .order_by(IntakeItem.created_at.asc())
            .all()
        )
        seg_svc = SourceSegmentService(self.db)
        segments_by_source: dict[UUID, list] = {}
        for seg in seg_svc.list_for_book(book.id):
            segments_by_source.setdefault(seg.source_id, []).append(seg)

        reference_ids = [
            value
            for item in items
            if (value := getattr(item, "reference_file_id", None)) is not None
        ]
        references = (
            self.db.query(ReferenceFile).filter(ReferenceFile.id.in_(reference_ids)).all()
            if reference_ids
            else []
        )
        references_by_id = {row.id: row for row in references}
        chunk_counts = {
            file_id: int(count)
            for file_id, count in (
                self.db.query(ReferenceChunk.file_id, func.count(ReferenceChunk.id))
                .filter(
                    ReferenceChunk.file_id.in_(reference_ids),
                    ReferenceChunk.active.is_(True),
                    ReferenceChunk.chunk_kind == "reference_material",
                )
                .group_by(ReferenceChunk.file_id)
                .all()
                if reference_ids
                else []
            )
        }
        used_stages_by_source: dict[str, set[str]] = {}
        snapshots = (
            self.db.query(GenerationContextSnapshot)
            .filter(GenerationContextSnapshot.book_id == book.id)
            .order_by(GenerationContextSnapshot.created_at.desc())
            .limit(200)
            .all()
        )
        for snapshot in snapshots:
            for source in snapshot.source_items or []:
                if not isinstance(source, dict):
                    continue
                source_id = str(source.get("source_id") or "").strip()
                if source_id:
                    used_stages_by_source.setdefault(source_id, set()).add(snapshot.source_module)

        out: list[dict] = []
        for item in items:
            summary = (item.parsed_preview or item.text_content or "")[:500] or None
            segs = segments_by_source.get(item.id, [])
            reference_file_id = getattr(item, "reference_file_id", None)
            reference_file = references_by_id.get(reference_file_id)
            out.append(
                {
                    "id": item.id,
                    "title": _source_title(item),
                    "type": _source_type(item),
                    "status": _source_status(item, reference_file),
                    "summary": summary,
                    "detected_roles": list(item.detected_roles or []),
                    "source_url": item.source_url,
                    "source_type": item.source_type,
                    "provider": item.provider,
                    "retrieved_at": item.retrieved_at,
                    "source_metadata": dict(item.source_metadata or {}),
                    "reference_file_id": reference_file_id,
                    "index_status": reference_file.parse_status.value if reference_file else None,
                    "lifecycle_status": reference_file.lifecycle_status.value if reference_file else None,
                    "chunk_count": chunk_counts.get(reference_file_id, 0),
                    "used_stages": sorted(used_stages_by_source.get(str(item.id), set())),
                    "segments": seg_svc.segments_to_dict(segs),
                }
            )
        return out

    def add_pasted_text(self, book: Book, text: str) -> IntakeItem:
        intake = self._ensure_intake(book)
        item = self._intake_items.add_text_item(intake, text, IntakeItemType.pasted_text)
        item.parsed_preview = text[:4000]
        self.db.flush()
        if len(text.strip()) >= 200:
            SourceSegmentService(self.db).extract_segments(book, item)
        return item

    def add_search_result(self, book: Book, result: dict) -> IntakeItem:
        """Save search metadata and snippet only; never persist fetched page content."""
        url = str(result.get("url") or "").strip()
        intake = self._ensure_intake(book)
        if url:
            existing = (
                self.db.query(IntakeItem)
                .filter(
                    IntakeItem.intake_id == intake.id,
                    IntakeItem.source_url == url,
                    IntakeItem.status != IntakeItemStatus.disabled,
                )
                .first()
            )
            if existing:
                return existing

        snippet = str(result.get("snippet") or "").strip()[:4000]
        title = str(result.get("title") or "未命名资料").strip()[:500]
        item = self._intake_items.add_text_item(intake, snippet, IntakeItemType.pasted_text)
        item.filename = title
        item.parsed_preview = snippet
        item.detected_roles = ["reference"]
        item.source_url = url or None
        item.source_type = str(result.get("source_type") or "web")[:64]
        item.provider = str(result.get("provider") or "unknown")[:64]
        item.retrieved_at = datetime.now(timezone.utc)
        item.source_metadata = {
            key: result.get(key)
            for key in (
                "authors",
                "publisher",
                "published_at",
                "year",
                "domain",
                "doi",
                "isbn",
                "external_id",
                "journal",
                "document_type",
                "credibility_hint",
                "citeability",
                "metadata_missing",
                "degraded",
            )
            if result.get(key) not in (None, "", [])
        }
        self.db.flush()
        return item

    def add_upload(
        self,
        book: Book,
        *,
        filename: str,
        content: bytes,
        owner_user_id,
        mime_type: str | None = None,
    ) -> IntakeItem:
        intake = self._ensure_intake(book)
        item = self._intake_items.add_upload_item(
            intake,
            filename=filename,
            content=content,
            owner_user_id=owner_user_id,
            mime_type=mime_type,
        )
        from app.services.sources.source_ingestion_service import SourceIngestionService

        SourceIngestionService(self.db).ensure_full_text_index(book, item)
        ft = _file_type(filename)
        if ft in {"pdf", "docx"} and item.asset_id:
            self._extract_preview(book, item, ft)
        preview = (item.parsed_preview or item.text_content or "").strip()
        if len(preview) >= 200:
            SourceSegmentService(self.db).extract_segments(book, item)
        return item

    def _extract_preview(self, book: Book, item: IntakeItem, file_type: str) -> None:
        if not item.asset_id:
            return
        try:
            from app.services.assets.binary_asset_service import BinaryAssetService
            from app.services.assets.temporary_workspace import TemporaryWorkspace

            asset = BinaryAssetService(self.db).get_asset_for_book(book_id=book.id, asset_id=item.asset_id)
            suffix = f".{file_type}"
            with TemporaryWorkspace().materialize(bytes(asset.content), suffix) as path:
                text = DocumentParserAgent.extract_text(str(path), file_type)
            preview = text[:8000]
            item.text_content = preview or item.text_content
            item.parsed_preview = preview[:4000] if preview else None
            item.status = IntakeItemStatus.parsed if preview.strip() else IntakeItemStatus.pending
            if preview.strip():
                self._intake_items._detect_roles(item, preview)
        except Exception:
            item.status = IntakeItemStatus.failed
        self.db.flush()

    def get_item(self, book_id: UUID, source_id: UUID) -> IntakeItem | None:
        item = self.db.query(IntakeItem).filter(IntakeItem.id == source_id).first()
        if not item:
            return None
        intake = self.db.query(ProjectIntake).filter(ProjectIntake.id == item.intake_id).first()
        if not intake or intake.book_id != book_id:
            return None
        return item

    def remove_source(self, book: Book, source_id: UUID) -> None:
        item = self.get_item(book.id, source_id)
        if not item:
            raise ValueError("Source not found")
        if item.status == IntakeItemStatus.disabled:
            return
        item.status = IntakeItemStatus.disabled
        reference_file_id = getattr(item, "reference_file_id", None)
        if reference_file_id:
            ref = self.db.get(ReferenceFile, reference_file_id)
            if ref and ref.book_id == book.id:
                ref.lifecycle_status = FileLifecycleStatus.disabled
                self.db.query(ReferenceChunk).filter(ReferenceChunk.file_id == ref.id).update({"active": False})
        self.db.flush()

    def read_source(self, book: Book, source_id: UUID) -> IntakeItem:
        item = self.get_item(book.id, source_id)
        if not item:
            raise ValueError("Source not found")
        if item.item_type == IntakeItemType.upload and item.asset_id:
            ft = _file_type(item.filename or "upload.bin")
            if ft in {"pdf", "docx", "txt", "md"}:
                self._extract_preview(book, item, ft if ft != "md" else "txt")
            if not getattr(item, "reference_file_id", None):
                from app.services.sources.source_ingestion_service import SourceIngestionService

                SourceIngestionService(self.db).ensure_full_text_index(book, item)
        reference_file_id = getattr(item, "reference_file_id", None)
        if reference_file_id:
            ref = self.db.get(ReferenceFile, reference_file_id)
            if ref and ref.book_id == book.id and ref.parse_status == ParseStatus.failed:
                ref.parse_status = ParseStatus.pending
                ref.lifecycle_status = FileLifecycleStatus.processing
                ref.error_message = None
        if not (item.parsed_preview or "").strip() and (item.text_content or "").strip():
            item.parsed_preview = item.text_content[:4000]
        preview = (item.parsed_preview or item.text_content or "").strip()
        if preview and len(preview) > 200:
            item.parsed_preview = self._summarize_text(preview)
        self.db.flush()
        SourceSegmentService(self.db).extract_segments(book, item)
        return item

    def _summarize_text(self, text: str) -> str:
        prompt = f"""请用 3-5 句话总结以下资料内容与可能用途，供书稿策划使用。只输出 JSON：
{{"summary":"..."}}

资料摘录：
{text[:6000]}"""
        try:
            out = LLMClient().chat_completion(
                [{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.2,
            )
            data = parse_llm_json(out)
            summary = str(data.get("summary") or "").strip()
            return summary[:4000] if summary else text[:4000]
        except Exception:
            return text[:4000]

    def sources_for_prompt(self, book: Book) -> str:
        rows = self.list_sources(book)
        if not rows:
            return "（暂无资料）"
        return json.dumps(
            [
                {
                    "id": str(r["id"]),
                    "title": r["title"],
                    "type": r["type"],
                    "status": r["status"],
                    "summary": (r.get("summary") or "")[:800],
                    "detected_roles": r.get("detected_roles") or [],
                    "segments": [
                        {
                            "segment_type": s.get("segment_type"),
                            "summary": (s.get("summary") or "")[:300],
                            "confidence": s.get("confidence"),
                            "needs_confirm": s.get("needs_confirm"),
                        }
                        for s in (r.get("segments") or [])[:8]
                    ],
                }
                for r in rows
            ],
            ensure_ascii=False,
        )
