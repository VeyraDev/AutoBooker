"""Unified writing context from confirmed intake artifacts."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.generation_context_snapshot import GenerationContextSnapshot
from app.models.intake import InputUnderstanding, ProjectIntake, WritingPlan, UnderstandingStatus, WritingPlanStatus
from app.models.material import MaterialTerm, OutlineConstraint, WritingRequirement
from app.models.writing_basis import WritingBasis, WritingBasisStatus
from app.models.book_format_strategy import BookFormatStrategy, FormatStrategyStatus
from app.services.writing.format_strategy_service import FormatStrategyService
from app.services.writing.writing_basis_service import WritingBasisService
from app.services.assistant.project_memory_service import ProjectMemoryService


class WritingContextBuilder:
    def __init__(self, db: Session):
        self.db = db

    def _confirmed_format_strategy(self, book_id: UUID) -> BookFormatStrategy | None:
        return (
            self.db.query(BookFormatStrategy)
            .filter(
                BookFormatStrategy.book_id == book_id,
                BookFormatStrategy.status == FormatStrategyStatus.confirmed,
            )
            .order_by(BookFormatStrategy.version.desc())
            .first()
        )

    def _active_format_strategy(self, book_id: UUID) -> BookFormatStrategy | None:
        confirmed = self._confirmed_format_strategy(book_id)
        if confirmed:
            return confirmed
        return (
            self.db.query(BookFormatStrategy)
            .filter(
                BookFormatStrategy.book_id == book_id,
                BookFormatStrategy.status == FormatStrategyStatus.draft,
            )
            .order_by(BookFormatStrategy.version.desc())
            .first()
        )

    def _confirmed_basis(self, book_id: UUID) -> WritingBasis | None:
        return (
            self.db.query(WritingBasis)
            .filter(WritingBasis.book_id == book_id, WritingBasis.status == WritingBasisStatus.confirmed)
            .order_by(WritingBasis.version.desc())
            .first()
        )

    def _confirmed_plan(self, book_id: UUID) -> tuple[InputUnderstanding | None, WritingPlan | None]:
        intake = (
            self.db.query(ProjectIntake)
            .filter(ProjectIntake.book_id == book_id, ProjectIntake.confirmed_writing_plan_id.isnot(None))
            .order_by(ProjectIntake.updated_at.desc())
            .first()
        )
        if not intake:
            return None, None
        understanding = None
        plan = None
        if intake.confirmed_understanding_id:
            understanding = self.db.query(InputUnderstanding).filter(InputUnderstanding.id == intake.confirmed_understanding_id).first()
        if intake.confirmed_writing_plan_id:
            plan = self.db.query(WritingPlan).filter(WritingPlan.id == intake.confirmed_writing_plan_id).first()
        return understanding, plan

    def _requirements(self, book_id: UUID, chapter_index: int | None = None) -> list[WritingRequirement]:
        q = self.db.query(WritingRequirement).filter(
            WritingRequirement.book_id == book_id,
            WritingRequirement.active.is_(True),
        )
        rows = q.all()
        if chapter_index is None:
            return rows
        return [r for r in rows if r.scope == "book" or r.chapter_index in (None, chapter_index)]

    def build_snapshot(self, book_id: UUID, *, chapter_index: int | None = None) -> dict:
        book = self.db.query(Book).filter(Book.id == book_id).first()
        basis = self._confirmed_basis(book_id)
        understanding, plan = self._confirmed_plan(book_id)
        requirements = self._requirements(book_id, chapter_index)
        terms = self.db.query(MaterialTerm).filter(MaterialTerm.book_id == book_id, MaterialTerm.active.is_(True)).all()
        constraints = (
            self.db.query(OutlineConstraint)
            .filter(OutlineConstraint.book_id == book_id, OutlineConstraint.active.is_(True))
            .all()
        )
        if chapter_index is not None:
            constraints = [c for c in constraints if c.chapter_index == chapter_index]
        plan_json = plan.plan_json if plan and isinstance(plan.plan_json, dict) else {}
        summary_json = understanding.summary_json if understanding and isinstance(understanding.summary_json, dict) else {}
        intent_json = summary_json.get("intent_json") if isinstance(summary_json.get("intent_json"), dict) else {}
        impact_map = plan.impact_map if plan and isinstance(plan.impact_map, dict) else {}
        intent_effects = list(intent_json.get("must_influence") or []) + list(impact_map.get("input_effects") or [])

        basis_dict = WritingBasisService(self.db).to_dict(basis) if basis else None
        ai_settings = dict(book.ai_inferred_settings or {}) if book else {}
        if basis:
            must_keep = list(basis.must_keep or [])
            must_avoid = list(basis.must_avoid or [])
            material_policy = list(basis.material_policy or [])
            outline_policy = list(basis.outline_policy or [])
        else:
            must_keep = list(plan_json.get("must_keep") or [])
            must_avoid = list(plan_json.get("must_avoid") or []) + list((understanding.avoid_rules or []) if understanding else [])
            material_policy = list(plan_json.get("material_policy") or [])
            outline_policy = []

        for item in ai_settings.get("material_policy") or []:
            s = str(item).strip()
            if s and s not in material_policy:
                material_policy.append(s)
        for item in ai_settings.get("outline_policy") or []:
            s = str(item).strip()
            if s and s not in outline_policy:
                outline_policy.append(s)

        format_strategy = self._active_format_strategy(book_id)
        format_svc = FormatStrategyService(self.db)
        format_dict = format_svc.to_dict(format_strategy)

        return {
            "book_id": str(book_id),
            "writing_basis_id": str(basis.id) if basis else None,
            "writing_basis": basis_dict,
            "format_strategy_id": str(format_strategy.id) if format_strategy else None,
            "format_strategy": format_dict,
            "understanding_id": str(understanding.id) if understanding else None,
            "writing_plan_id": str(plan.id) if plan else None,
            "requirement_ids": [str(r.id) for r in requirements],
            "outline_constraint_ids": [str(c.id) for c in constraints],
            "requirements": [{"id": str(r.id), "content": r.content, "strength": r.strength, "scope": r.scope} for r in requirements],
            "material_terms": [t.term for t in terms[:50]],
            "outline_constraints": [
                {"chapter_index": c.chapter_index, "chapter_title": c.chapter_title, "locked_sections": c.locked_sections}
                for c in constraints
            ],
            "plan_json": plan_json,
            "intent_json": intent_json,
            "impact_map": impact_map,
            "intent_effects": intent_effects,
            "legacy_user_material": (book.user_material or "")[:4000] if book else "",
            "plan_text": plan.user_facing_text if plan else "",
            "understanding_text": understanding.user_facing_text if understanding else "",
            "must_keep": must_keep,
            "must_avoid": must_avoid,
            "material_policy": material_policy,
            "outline_policy": outline_policy,
            "chapter_index": chapter_index,
        }

    def to_prompt_block(self, snap: dict) -> str:
        parts: list[str] = []
        basis = snap.get("writing_basis") if isinstance(snap.get("writing_basis"), dict) else None
        if basis:
            basis_lines: list[str] = []
            for label, key in (
                ("方向", "direction"),
                ("书稿承诺", "book_promise"),
                ("目标读者", "target_readers"),
                ("读者收益", "reader_outcome"),
                ("内容范围", "scope"),
                ("专业深度", "depth"),
                ("语言风格", "voice"),
            ):
                val = basis.get(key)
                if val:
                    basis_lines.append(f"- {label}：{val}")
            for label, key in (
                ("资料使用规则", "material_policy"),
                ("大纲规则", "outline_policy"),
                ("引用要求", "citation_policy"),
                ("图表要求", "figure_policy"),
            ):
                items = basis.get(key) or []
                if items:
                    basis_lines.append(f"- {label}：")
                    basis_lines.extend(f"  · {x}" for x in items[:10] if str(x).strip())
            if basis_lines:
                parts.append("【写作依据】\n" + "\n".join(basis_lines))
        elif snap.get("understanding_text"):
            parts.append(f"【已确认理解】\n{snap['understanding_text']}")
            if snap.get("plan_text"):
                parts.append(f"【写作方案】\n{snap['plan_text']}")
        elif snap.get("plan_text"):
            parts.append(f"【写作方案】\n{snap['plan_text']}")
        effects = snap.get("intent_effects") or []
        if effects:
            lines: list[str] = []
            for item in effects[:20]:
                if isinstance(item, dict):
                    ref = str(item.get("input_ref") or "").strip()
                    effect = str(item.get("writing_effect") or "").strip()
                    applies_to = item.get("applies_to") if isinstance(item.get("applies_to"), list) else []
                    scope = "、".join(str(x) for x in applies_to[:4] if x)
                    line = effect or ref
                    if ref and effect:
                        line = f"{ref} -> {effect}"
                    if scope:
                        line = f"{line}（影响：{scope}）"
                else:
                    line = str(item).strip()
                if line:
                    lines.append(line[:300])
            if lines:
                parts.append("【输入意图对写作的影响】\n" + "\n".join(f"- {x}" for x in lines))
        must_keep = snap.get("must_keep") or []
        must_avoid = snap.get("must_avoid") or []
        if must_keep:
            parts.append("【必须保留】\n" + "\n".join(f"- {x}" for x in must_keep[:20]))
        if must_avoid:
            parts.append("【必须避免】\n" + "\n".join(f"- {x}" for x in must_avoid[:20]))
        book_id_raw = snap.get("book_id")
        if book_id_raw:
            memory_block = ProjectMemoryService(self.db).to_prompt_block(UUID(str(book_id_raw)), confirmed_only=True)
            if memory_block:
                parts.append(f"【项目长期记忆】\n{memory_block}")
        policy = snap.get("material_policy") or []
        if policy:
            parts.append("【资料使用策略】\n" + "\n".join(f"- {x}" for x in policy[:10]))
        outline_policy = snap.get("outline_policy") or []
        if outline_policy:
            parts.append("【大纲规则】\n" + "\n".join(f"- {x}" for x in outline_policy[:10]))
        format_strategy = snap.get("format_strategy") if isinstance(snap.get("format_strategy"), dict) else None
        if format_strategy:
            summary_lines: list[str] = []
            for label, key in (
                ("书级固定栏目", "book_level_columns"),
                ("条件栏目", "conditional_columns"),
            ):
                cols = format_strategy.get(key) or []
                if not cols:
                    continue
                summary_lines.append(f"{label}：")
                for col in cols[:6]:
                    if isinstance(col, dict):
                        name = col.get("column_name") or ""
                        purpose = col.get("purpose") or ""
                        if name:
                            summary_lines.append(f"  · {name}（{purpose[:80]}）" if purpose else f"  · {name}")
            forbidden = format_strategy.get("forbidden_patterns") or []
            if forbidden:
                summary_lines.append("禁止模板化：" + "；".join(str(x) for x in forbidden[:5]))
            if summary_lines:
                parts.append("【全书体例与栏目】\n" + "\n".join(summary_lines))
        chapter_index = snap.get("chapter_index")
        if chapter_index is not None and format_strategy:
            fs_id = snap.get("format_strategy_id")
            fs_row = None
            if fs_id:
                fs_row = self.db.query(BookFormatStrategy).filter(BookFormatStrategy.id == UUID(str(fs_id))).first()
            if fs_row and fs_row.status == FormatStrategyStatus.confirmed:
                chapter_block = FormatStrategyService(self.db).chapter_format_block(fs_row, int(chapter_index))
                if chapter_block:
                    parts.append(f"【本章栏目策略】\n{chapter_block}")
        reqs = snap.get("requirements") or []
        if reqs:
            parts.append("【写作要求】\n" + "\n".join(f"- ({r['strength']}) {r['content'][:200]}" for r in reqs[:15]))
        terms = snap.get("material_terms") or []
        if terms:
            parts.append("【术语】\n" + "、".join(terms[:30]))
        legacy = (snap.get("legacy_user_material") or "").strip()
        if legacy and not snap.get("writing_plan_id") and not snap.get("writing_basis_id"):
            parts.append(f"【用户资料（兼容）】\n{legacy[:3000]}")
        return "\n\n".join(parts).strip()

    def context_hash(self, snap: dict) -> str:
        payload = {
            "writing_basis_id": snap.get("writing_basis_id"),
            "understanding_id": snap.get("understanding_id"),
            "writing_plan_id": snap.get("writing_plan_id"),
            "requirement_ids": snap.get("requirement_ids"),
            "outline_constraint_ids": snap.get("outline_constraint_ids"),
            "must_avoid": snap.get("must_avoid"),
            "must_keep": snap.get("must_keep"),
            "intent_json": snap.get("intent_json"),
            "impact_map": snap.get("impact_map"),
            "intent_effects": snap.get("intent_effects"),
            "format_strategy_id": snap.get("format_strategy_id"),
            "chapter_index": snap.get("chapter_index"),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def persist_snapshot(self, book_id: UUID, source_module: str, snap: dict) -> GenerationContextSnapshot:
        excerpt = self.to_prompt_block(snap)[:4000]
        row = GenerationContextSnapshot(
            book_id=book_id,
            understanding_id=UUID(snap["understanding_id"]) if snap.get("understanding_id") else None,
            writing_plan_id=UUID(snap["writing_plan_id"]) if snap.get("writing_plan_id") else None,
            writing_basis_id=UUID(snap["writing_basis_id"]) if snap.get("writing_basis_id") else None,
            format_strategy_id=UUID(snap["format_strategy_id"]) if snap.get("format_strategy_id") else None,
            requirement_ids=snap.get("requirement_ids") or [],
            outline_constraint_ids=snap.get("outline_constraint_ids") or [],
            context_hash=self.context_hash(snap),
            prompt_excerpt=excerpt,
            source_module=source_module,
            chapter_index=snap.get("chapter_index"),
        )
        self.db.add(row)
        self.db.flush()
        return row

    def build_for_outline(self, book_id: UUID) -> dict:
        snap = self.build_snapshot(book_id)
        self.persist_snapshot(book_id, "outline", snap)
        return snap

    def build_for_narrative(self, book_id: UUID) -> dict:
        snap = self.build_snapshot(book_id)
        self.persist_snapshot(book_id, "narrative", snap)
        return snap

    def build_for_chapter(self, book_id: UUID, chapter_index: int) -> dict:
        snap = self.build_snapshot(book_id, chapter_index=chapter_index)
        self.persist_snapshot(book_id, "chapter", snap)
        return snap

    def build_for_review(self, book_id: UUID) -> dict:
        snap = self.build_snapshot(book_id)
        self.persist_snapshot(book_id, "review", snap)
        return snap

    def chapter_format_block(self, book_id: UUID, chapter_index: int) -> str:
        strategy = self._confirmed_format_strategy(book_id)
        return FormatStrategyService(self.db).chapter_format_block(strategy, chapter_index)

    def auto_progress_allowed(self, book_id: UUID) -> bool:
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book or not book.creation_origin:
            return True
        from app.models.intake import IntakeStatus, ProjectIntake

        intake = (
            self.db.query(ProjectIntake)
            .filter(
                ProjectIntake.book_id == book_id,
                ProjectIntake.status != IntakeStatus.superseded,
            )
            .order_by(ProjectIntake.created_at.desc())
            .first()
        )
        if intake and intake.status == IntakeStatus.confirmed:
            return True
        if intake and (intake.raw_goal_text or "").strip():
            return True
        understanding, plan = self._confirmed_plan(book_id)
        return (
            understanding is not None
            and plan is not None
            and understanding.status == UnderstandingStatus.confirmed
            and plan.status == WritingPlanStatus.confirmed
        )
