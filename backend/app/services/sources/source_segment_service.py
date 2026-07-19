"""Extract and manage source segments from mixed intake materials."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.models.book import Book
from app.models.intake import IntakeItem
from app.models.source_segment import SegmentType, SourceSegment
from app.prompts.assistant.extract_signals import EXTRACT_SEGMENTS_INSTRUCTION
from app.services.sources.content_extractors import heuristic_segments
from app.utils.json_llm import parse_llm_json

_VALID_TYPES = {t.value for t in SegmentType}

_OUTLINE_POLICIES: dict[str, str] = {
    "outline": "严格保留用户提供的目录/大纲章序与章标题，仅可补充摘要与字数",
}

_MATERIAL_POLICIES: dict[str, str] = {
    "manuscript": "已有初稿段落优先保留原意，扩写时不得擅自删改核心论述",
    "chapter_draft": "章节草稿作为正文底稿，优化表达但保持结构",
    "bibliography": "参考文献列表仅作引用来源，不当作正文素材逐字照搬",
    "requirement": "写作要求与禁止事项必须遵守",
    "style_sample": "文风样章仅作语气参考，不复制具体内容",
}


def _coerce_segment_type(raw: str) -> SegmentType | None:
    key = (raw or "").strip().lower()
    if key in _VALID_TYPES:
        return SegmentType(key)
    return None


def _item_full_text(item: IntakeItem) -> str:
    return ((item.parsed_preview or "") + "\n" + (item.text_content or "")).strip()


class SourceSegmentService:
    def __init__(self, db: Session):
        self.db = db

    def list_for_source(self, source_id: UUID) -> list[SourceSegment]:
        return (
            self.db.query(SourceSegment)
            .filter(SourceSegment.source_id == source_id)
            .order_by(SourceSegment.confidence.desc(), SourceSegment.created_at.asc())
            .all()
        )

    def list_for_book(self, book_id: UUID) -> list[SourceSegment]:
        return (
            self.db.query(SourceSegment)
            .filter(SourceSegment.book_id == book_id)
            .order_by(SourceSegment.source_id, SourceSegment.confidence.desc())
            .all()
        )

    def extract_segments(self, book: Book, item: IntakeItem, *, force: bool = False) -> list[SourceSegment]:
        text = _item_full_text(item)
        if len(text) < 200:
            return self.list_for_source(item.id)
        existing = self.list_for_source(item.id)
        if existing and not force:
            return existing

        self.db.query(SourceSegment).filter(SourceSegment.source_id == item.id).delete()
        raw_segments = self._llm_extract(text)
        if len(raw_segments) < 1:
            raw_segments = heuristic_segments(text)
        created: list[SourceSegment] = []
        for row in raw_segments[:10]:
            seg_type = _coerce_segment_type(str(row.get("segment_type") or ""))
            if not seg_type:
                continue
            summary = str(row.get("summary") or "").strip()
            if not summary:
                continue
            try:
                confidence = float(row.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            confidence = max(0.0, min(1.0, confidence))
            seg = SourceSegment(
                book_id=book.id,
                source_id=item.id,
                segment_type=seg_type,
                summary=summary[:2000],
                locator=str(row.get("locator") or "").strip()[:500] or None,
                confidence=confidence,
                suggested_usage=str(row.get("suggested_usage") or "").strip()[:1000] or None,
                excerpt=str(row.get("excerpt") or "").strip()[:500] or None,
                user_confirmed=True if confidence >= 0.7 else None,
            )
            self.db.add(seg)
            created.append(seg)
        self.db.flush()
        if created:
            self.sync_policies_to_book(book)
        return created

    def _llm_extract(self, text: str) -> list[dict]:
        prompt = f"""{EXTRACT_SEGMENTS_INSTRUCTION}

资料全文（截断）：
{text[:12000]}"""
        try:
            out = LLMClient().chat_completion(
                [{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.2,
            )
            data = parse_llm_json(out)
            segments = data.get("segments") or []
            return [s for s in segments if isinstance(s, dict)]
        except Exception:
            return []

    def confirm_segment(self, book: Book, segment_id: UUID, *, confirmed: bool) -> SourceSegment:
        seg = self.db.query(SourceSegment).filter(SourceSegment.id == segment_id, SourceSegment.book_id == book.id).first()
        if not seg:
            raise ValueError("Segment not found")
        seg.user_confirmed = confirmed
        self.db.flush()
        self.sync_policies_to_book(book)
        return seg

    def sync_policies_to_book(self, book: Book) -> None:
        segments = (
            self.db.query(SourceSegment)
            .filter(SourceSegment.book_id == book.id)
            .all()
        )
        outline_rules: list[str] = []
        material_rules: list[str] = []
        for seg in segments:
            if seg.user_confirmed is False:
                continue
            if seg.user_confirmed is None and (seg.confidence or 0) < 0.7:
                continue
            t = seg.segment_type.value
            if t in _OUTLINE_POLICIES:
                rule = _OUTLINE_POLICIES[t]
                if rule not in outline_rules:
                    outline_rules.append(rule)
            if t in _MATERIAL_POLICIES:
                rule = _MATERIAL_POLICIES[t]
                if rule not in material_rules:
                    material_rules.append(rule)
            if seg.suggested_usage and seg.suggested_usage not in material_rules:
                material_rules.append(seg.suggested_usage[:500])

        settings = dict(book.ai_inferred_settings or {})
        if outline_rules:
            settings["outline_policy"] = outline_rules[:12]
        if material_rules:
            settings["material_policy"] = material_rules[:12]
        settings["source_segment_count"] = len(segments)
        book.ai_inferred_settings = settings
        self.db.flush()

    def segments_to_dict(self, segments: list[SourceSegment]) -> list[dict]:
        return [
            {
                "id": seg.id,
                "source_id": seg.source_id,
                "segment_type": seg.segment_type.value,
                "summary": seg.summary,
                "locator": seg.locator,
                "confidence": seg.confidence,
                "suggested_usage": seg.suggested_usage,
                "excerpt": seg.excerpt,
                "user_confirmed": seg.user_confirmed,
                "needs_confirm": seg.user_confirmed is None and (seg.confidence or 0) < 0.7,
            }
            for seg in segments
        ]
