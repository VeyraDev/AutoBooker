"""Structured context contract shared by outline, narrative, writing and review."""

from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.intake import IntakeItem, IntakeItemStatus
from app.models.reference import FileLifecycleStatus, ParseStatus, ReferenceFile
from app.models.source_segment import SegmentType, SourceSegment
from app.services.sources.stage_source_context_service import StageSourceContextService
from app.services.writing.writing_context_builder import WritingContextBuilder


_ROLE_TYPES: dict[str, set[SegmentType]] = {
    "outline": {SegmentType.outline, SegmentType.requirement, SegmentType.manuscript, SegmentType.chapter_draft},
    "narrative": {SegmentType.requirement, SegmentType.style_sample},
    "chapter": {SegmentType.requirement},
    "review": {SegmentType.requirement},
}

_ROLE_USAGE = {
    SegmentType.outline: "structure_candidate",
    SegmentType.requirement: "writing_constraint",
    SegmentType.manuscript: "structure_hint",
    SegmentType.chapter_draft: "structure_hint",
    SegmentType.style_sample: "style_constraint",
}


def _role_source_is_effective(
    source: IntakeItem | None,
    reference_file: ReferenceFile | None,
) -> bool:
    if source is None or source.status != IntakeItemStatus.parsed:
        return False
    if source.reference_file_id is None:
        return True
    return bool(
        reference_file
        and reference_file.parse_status == ParseStatus.done
        and reference_file.lifecycle_status == FileLifecycleStatus.effective
    )


class StageContextBuilder:
    """Build and persist one stage-specific context without full-library injection."""

    def __init__(self, db: Session):
        self.db = db
        self.sources = StageSourceContextService(db)
        self.writing = WritingContextBuilder(db)

    def build(
        self,
        book_id: UUID,
        *,
        stage: str,
        query: str,
        chapter_index: int | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        if stage not in {"outline", "narrative", "chapter", "review"}:
            raise ValueError(f"Unsupported stage: {stage}")
        limit = top_k or {"outline": 10, "narrative": 6, "chapter": 12, "review": 16}[stage]
        if stage == "review":
            retrieved = self.sources.retrieve_for_review(
                book_id,
                query=query,
                chapter_index=chapter_index,
                top_k=limit,
            )
        else:
            retrieved = self.sources.retrieve(
                book_id,
                stage=stage,
                query=query,
                top_k=limit,
            )
        role_items = self._role_items(book_id, stage)[:8]
        primary_items, secondary_items = (
            (retrieved, role_items) if stage == "review" else (role_items, retrieved)
        )
        source_items = self.sources.merge_usage_items(
            primary_items,
            secondary_items,
            limit=limit + len(role_items),
        )
        if stage == "outline":
            snapshot = self.writing.build_for_outline(book_id, source_items=source_items)
        elif stage == "narrative":
            snapshot = self.writing.build_for_narrative(book_id, source_items=source_items)
        elif stage == "chapter":
            if chapter_index is None:
                raise ValueError("chapter_index required for chapter context")
            snapshot = self.writing.build_for_chapter(
                book_id,
                chapter_index,
                source_items=source_items,
            )
        else:
            snapshot = self.writing.build_for_review(book_id, source_items=source_items)

        reference_materials = [
            item for item in source_items if item.get("usage_type") == "reference_evidence"
        ]
        citations = [item for item in source_items if item.get("source_kind") == "citation"]
        structure_materials = [
            item
            for item in source_items
            if item.get("usage_type") in {"structure_candidate", "structure_hint"}
        ]
        style_samples = [item for item in source_items if item.get("usage_type") == "style_constraint"]
        source_counts = Counter(str(item.get("source_kind") or "unknown") for item in source_items)
        usage_records = [
            {
                "stage": stage,
                "chapter_index": chapter_index,
                "source_id": item.get("source_id"),
                "segment_id": item.get("segment_id") or item.get("chunk_id"),
                "citation_id": item.get("citation_id"),
                "usage_type": item.get("usage_type"),
                "usage_origin": item.get("usage_origin"),
                "reason": item.get("reason"),
                "generation_id": item.get("generation_id"),
                "locator": item.get("locator"),
            }
            for item in source_items
        ]
        known_gaps: list[str] = []
        if stage in {"outline", "chapter", "review"} and not reference_materials and not citations:
            known_gaps.append("当前阶段未检索到相关事实资料或文献证据")
        if citations and not any(item.get("verification_status") == "verified" for item in citations):
            known_gaps.append("相关文献尚无已核验条目，具体主张需保守处理")

        return {
            "stage": stage,
            "chapter_index": chapter_index,
            "book_settings": {
                "writing_basis": snapshot.get("writing_basis"),
                "format_strategy": snapshot.get("format_strategy"),
                "intent_effects": snapshot.get("intent_effects") or [],
            },
            "writing_requirements": snapshot.get("requirements") or [],
            "structure_materials": structure_materials,
            "reference_materials": reference_materials,
            "citations": citations,
            "terminology": snapshot.get("material_terms") or [],
            "style_samples": style_samples,
            "source_policy": {
                "source_conditions": dict(source_counts),
                "material_policy": snapshot.get("material_policy") or [],
                "must_avoid": snapshot.get("must_avoid") or [],
            },
            "known_gaps": known_gaps,
            "usage_records": usage_records,
            "source_items": source_items,
            "snapshot": snapshot,
            "prompt_block": self.writing.to_prompt_block(snapshot),
        }

    def _role_items(self, book_id: UUID, stage: str) -> list[dict[str, Any]]:
        role_types = _ROLE_TYPES.get(stage) or set()
        if not role_types:
            return []
        rows = (
            self.db.query(SourceSegment)
            .filter(
                SourceSegment.book_id == book_id,
                SourceSegment.segment_type.in_(role_types),
            )
            .order_by(SourceSegment.confidence.desc(), SourceSegment.created_at.desc())
            .limit(30)
            .all()
        )
        rows = [
            row
            for row in rows
            if row.user_confirmed is not False
            and (row.user_confirmed is True or float(row.confidence or 0) >= 0.7)
        ]
        source_ids = [row.source_id for row in rows]
        source_rows = (
            self.db.query(IntakeItem).filter(IntakeItem.id.in_(source_ids)).all()
            if source_ids
            else []
        )
        source_map = {row.id: row for row in source_rows}
        reference_ids = [row.reference_file_id for row in source_rows if row.reference_file_id]
        reference_rows = (
            self.db.query(ReferenceFile).filter(ReferenceFile.id.in_(reference_ids)).all()
            if reference_ids
            else []
        )
        reference_map = {row.id: row for row in reference_rows}
        items: list[dict[str, Any]] = []
        for row in rows:
            source = source_map.get(row.source_id)
            reference_file = reference_map.get(source.reference_file_id) if source else None
            if not _role_source_is_effective(source, reference_file):
                continue
            role = row.segment_type
            items.append(
                {
                    "source_kind": "source_segment",
                    "source_id": str(row.source_id),
                    "segment_id": str(row.id),
                    "title": getattr(source, "filename", None) or f"已识别{role.value}片段",
                    "locator": row.locator or "资料角色识别片段",
                    "content": (row.excerpt or row.summary or "")[:1800],
                    "score": float(row.confidence or 0),
                    "directly_quotable": False,
                    "role": role.value,
                    "usage_type": _ROLE_USAGE.get(role, "stage_constraint"),
                    "usage_origin": "segment_role",
                    "reason": row.suggested_usage or f"片段角色识别为 {role.value}",
                    "stage": stage,
                }
            )
        return items
