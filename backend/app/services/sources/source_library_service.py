"""Unified source library over intake items."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.document_parser import DocumentParserAgent
from app.llm.client import LLMClient
from app.models.book import Book, CreationOrigin
from app.models.intake import IntakeItem, IntakeItemStatus, IntakeItemType, IntakeStatus, ProjectIntake
from app.services.intake.intake_services import IntakeItemService
from app.services.sources.source_segment_service import SourceSegmentService
from app.utils.json_llm import parse_llm_json


def _file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext or "bin"


def _source_status(item: IntakeItem) -> str:
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

        out: list[dict] = []
        for item in items:
            summary = (item.parsed_preview or item.text_content or "")[:500] or None
            segs = segments_by_source.get(item.id, [])
            out.append(
                {
                    "id": item.id,
                    "title": _source_title(item),
                    "type": _source_type(item),
                    "status": _source_status(item),
                    "summary": summary,
                    "detected_roles": list(item.detected_roles or []),
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
        self.db.flush()

    def read_source(self, book: Book, source_id: UUID) -> IntakeItem:
        item = self.get_item(book.id, source_id)
        if not item:
            raise ValueError("Source not found")
        if item.item_type == IntakeItemType.upload and item.asset_id:
            ft = _file_type(item.filename or "upload.bin")
            if ft in {"pdf", "docx", "txt", "md"}:
                self._extract_preview(book, item, ft if ft != "md" else "txt")
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
