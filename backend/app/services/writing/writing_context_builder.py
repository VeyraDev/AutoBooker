"""Unified writing context from confirmed intake artifacts."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.citation import Citation
from app.models.generation_context_snapshot import GenerationContextSnapshot
from app.models.intake import InputUnderstanding, ProjectIntake, WritingPlan, UnderstandingStatus, WritingPlanStatus
from app.models.material import MaterialTerm, OutlineConstraint, WritingRequirement
from app.models.reference import FileLifecycleStatus, ParseStatus, ReferenceFile
from app.models.writing_basis import WritingBasis, WritingBasisStatus
from app.services.writing.writing_basis_service import WritingBasisService
from app.services.assistant.project_memory_service import ProjectMemoryService
from app.services.citation_verification import persisted_citation_verification_dict
from app.services.review.review_rule_evolution import (
    build_confirmed_rule_prompt_block,
    build_rule_candidate_prompt_block,
    get_rule_candidates_for_book,
    list_confirmed_review_rules,
)


class WritingContextBuilder:
    def __init__(self, db: Session):
        self.db = db

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
        rows = self._only_effective_file_rows(q.all())
        if chapter_index is None:
            return rows
        return [r for r in rows if r.scope == "book" or r.chapter_index in (None, chapter_index)]

    def _only_effective_file_rows(self, rows: list) -> list:
        file_ids = {row.source_file_id for row in rows if getattr(row, "source_file_id", None)}
        if not file_ids:
            return rows
        effective_ids = {
            row.id
            for row in self.db.query(ReferenceFile)
            .filter(
                ReferenceFile.id.in_(file_ids),
                ReferenceFile.parse_status == ParseStatus.done,
                ReferenceFile.lifecycle_status == FileLifecycleStatus.effective,
            )
            .all()
        }
        return [
            row
            for row in rows
            if getattr(row, "source_file_id", None) is None or row.source_file_id in effective_ids
        ]

    def _citation_summaries(self, book_id: UUID) -> list[dict]:
        rows = (
            self.db.query(Citation)
            .filter(Citation.book_id == book_id)
            .order_by(Citation.created_at.desc())
            .limit(200)
            .all()
        )
        summaries: list[dict] = []
        for row in rows:
            verification = persisted_citation_verification_dict(row)
            summaries.append(
                {
                    "id": str(row.id),
                    "title": row.title or "",
                    "authors": row.authors or [],
                    "year": row.year,
                    "journal": row.journal or "",
                    "doi": row.doi or "",
                    "url": row.url or "",
                    "document_type": row.document_type,
                    "metadata_status": row.metadata_status,
                    "source": row.source.value if hasattr(row.source, "value") else str(row.source),
                    "source_file_id": str(row.source_file_id) if row.source_file_id else None,
                    "volume": row.volume,
                    "issue": row.issue,
                    "pages": row.pages,
                    "has_abstract": bool((row.abstract_preview or "").strip()),
                    "verification_status": verification.get("verification_status"),
                    "source_match": verification.get("source_match"),
                    "missing_fields": verification.get("missing_fields") or [],
                    "recommended_search_query": verification.get("recommended_search_query") or "",
                    "verification": verification,
                }
            )
        return summaries

    def build_snapshot(self, book_id: UUID, *, chapter_index: int | None = None) -> dict:
        book = self.db.query(Book).filter(Book.id == book_id).first()
        basis = self._confirmed_basis(book_id)
        understanding, plan = self._confirmed_plan(book_id)
        requirements = self._requirements(book_id, chapter_index)
        terms = self._only_effective_file_rows(
            self.db.query(MaterialTerm).filter(MaterialTerm.book_id == book_id, MaterialTerm.active.is_(True)).all()
        )
        constraints = self._only_effective_file_rows(
            self.db.query(OutlineConstraint)
            .filter(OutlineConstraint.book_id == book_id, OutlineConstraint.active.is_(True))
            .all()
        )
        if chapter_index is not None:
            constraints = [c for c in constraints if c.chapter_index == chapter_index]
        try:
            review_rule_candidates = get_rule_candidates_for_book(self.db, book_id)
        except Exception:
            review_rule_candidates = []
        try:
            confirmed_review_rules = list_confirmed_review_rules(self.db, book_id)
        except Exception:
            confirmed_review_rules = []
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

        source_materials: dict = {}
        try:
            from app.services.sources.source_outline_bridge import materials_from_outline_contract

            if book:
                source_materials = materials_from_outline_contract(self.db, book)
        except Exception:
            source_materials = {}

        return {
            "book_id": str(book_id),
            "writing_basis_id": str(basis.id) if basis else None,
            "writing_basis": basis_dict,
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
            "source_outline_blocks": source_materials.get("source_outline_blocks") or [],
            "source_requirement_blocks": source_materials.get("source_requirement_blocks") or [],
            "source_manuscript_blocks": source_materials.get("source_manuscript_blocks") or [],
            "source_reference_outline_blocks": source_materials.get("source_reference_outline_blocks") or [],
            "outline_contract": source_materials.get("contract"),
            "citations": self._citation_summaries(book_id),
            "review_rule_candidates": review_rule_candidates,
            "confirmed_review_rules": confirmed_review_rules,
            "source_items": [],
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
        citations = snap.get("citations") or []
        if citations:
            lines: list[str] = []
            for item in citations[:30]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                authors = "、".join(str(a) for a in (item.get("authors") or [])[:3] if str(a).strip())
                year = item.get("year") or "n.d."
                status = item.get("verification_status") or item.get("metadata_status") or "needs_verification"
                missing = item.get("missing_fields") or []
                missing_text = f"；缺字段：{'、'.join(str(x) for x in missing[:4])}" if missing else ""
                query = str(item.get("recommended_search_query") or "").strip()
                query_text = f"；建议检索：{query[:120]}" if query and status in {"needs_verification", "mismatch", "unreachable"} else ""
                prefix = f"{authors}，" if authors else ""
                lines.append(f"- {prefix}{title}（{year}；核验：{status}{missing_text}{query_text}）")
            if lines:
                parts.append("【本书文献与核验状态】\n" + "\n".join(lines))
        confirmed_rule_block = build_confirmed_rule_prompt_block(snap.get("confirmed_review_rules") or [])
        if confirmed_rule_block:
            parts.append(confirmed_rule_block)
        rule_candidate_block = build_rule_candidate_prompt_block(snap.get("review_rule_candidates") or [])
        if rule_candidate_block:
            parts.append(rule_candidate_block)
        outline_policy = snap.get("outline_policy") or []
        if outline_policy:
            parts.append("【大纲规则】\n" + "\n".join(f"- {x}" for x in outline_policy[:10]))
        if snap.get("source_outline_blocks"):
            parts.append(
                "【已确认主大纲】\n" + "\n---\n".join(str(x)[:2000] for x in snap["source_outline_blocks"][:2])
            )
        if snap.get("source_reference_outline_blocks"):
            parts.append(
                "【参考大纲】\n"
                + "\n---\n".join(str(x)[:1500] for x in snap["source_reference_outline_blocks"][:2])
            )
        if snap.get("source_requirement_blocks"):
            parts.append(
                "【已确认写作要求】\n"
                + "\n---\n".join(str(x)[:2000] for x in snap["source_requirement_blocks"][:2])
            )
        if snap.get("source_manuscript_blocks"):
            parts.append(
                "【初稿结构线索】\n"
                + "\n---\n".join(str(x)[:1200] for x in snap["source_manuscript_blocks"][:2])
            )
        reqs = snap.get("requirements") or []
        if reqs:
            parts.append("【写作要求】\n" + "\n".join(f"- ({r['strength']}) {r['content'][:200]}" for r in reqs[:15]))
        terms = snap.get("material_terms") or []
        if terms:
            parts.append("【术语】\n" + "、".join(terms[:30]))
        legacy = (snap.get("legacy_user_material") or "").strip()
        if legacy and not snap.get("writing_plan_id") and not snap.get("writing_basis_id"):
            parts.append(f"【用户资料（兼容）】\n{legacy[:3000]}")
        source_items = snap.get("source_items") or []
        if source_items:
            from app.services.sources.stage_source_context_service import StageSourceContextService

            source_block = StageSourceContextService.format_for_prompt(source_items, char_budget=8000)
            if source_block:
                parts.append(source_block)
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
            "chapter_index": snap.get("chapter_index"),
            "citations": snap.get("citations"),
            "review_rule_candidates": snap.get("review_rule_candidates"),
            "confirmed_review_rules": snap.get("confirmed_review_rules"),
            "source_items": snap.get("source_items") or [],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def persist_snapshot(self, book_id: UUID, source_module: str, snap: dict) -> GenerationContextSnapshot:
        excerpt = self.to_prompt_block(snap)[:4000]
        row = GenerationContextSnapshot(
            book_id=book_id,
            understanding_id=UUID(snap["understanding_id"]) if snap.get("understanding_id") else None,
            writing_plan_id=UUID(snap["writing_plan_id"]) if snap.get("writing_plan_id") else None,
            writing_basis_id=UUID(snap["writing_basis_id"]) if snap.get("writing_basis_id") else None,
            requirement_ids=snap.get("requirement_ids") or [],
            outline_constraint_ids=snap.get("outline_constraint_ids") or [],
            source_items=snap.get("source_items") or [],
            context_hash=self.context_hash(snap),
            prompt_excerpt=excerpt,
            source_module=source_module,
            chapter_index=snap.get("chapter_index"),
        )
        self.db.add(row)
        self.db.flush()
        persisted_items: list[dict] = []
        for raw in snap.get("source_items") or []:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            item["generation_id"] = item.get("generation_id") or str(row.id)
            persisted_items.append(item)
        row.source_items = persisted_items
        return row

    # Stage whitelist: which source/context keys may enter each generation stage
    _STAGE_ALLOW: dict[str, frozenset[str]] = {
        "outline": frozenset(
            {
                "writing_basis",
                "writing_basis_id",
                "requirements",
                "requirement_ids",
                "outline_constraints",
                "outline_constraint_ids",
                "must_keep",
                "must_avoid",
                "material_policy",
                "outline_policy",
                "intent_effects",
                "plan_text",
                "understanding_text",
                "source_outline_blocks",
                "source_reference_outline_blocks",
                "source_requirement_blocks",
                "source_manuscript_blocks",  # only when contract says structure_hint_only
                "outline_contract",
                "material_terms",
                "source_items",
            }
        ),
        "narrative": frozenset(
            {
                "writing_basis",
                "writing_basis_id",
                "requirements",
                "must_keep",
                "must_avoid",
                "material_policy",
                "outline_policy",
                "intent_effects",
                "plan_text",
                "understanding_text",
                "source_requirement_blocks",
                "material_terms",
                "source_items",
            }
        ),
        "chapter": frozenset(
            {
                "writing_basis",
                "writing_basis_id",
                "requirements",
                "outline_constraints",
                "must_keep",
                "must_avoid",
                "material_policy",
                "intent_effects",
                "source_requirement_blocks",
                "material_terms",
                "chapter_index",
                "source_items",
            }
        ),
        "review": frozenset(
            {
                "writing_basis",
                "writing_basis_id",
                "requirements",
                "must_keep",
                "must_avoid",
                "material_policy",
                "citation_policy",
                "citations",
                "review_rule_candidates",
                "confirmed_review_rules",
                "source_requirement_blocks",
                "material_terms",
                "source_items",
            }
        ),
    }

    def apply_stage_whitelist(self, snap: dict, stage: str) -> dict:
        allow = self._STAGE_ALLOW.get(stage)
        if not allow:
            return snap
        meta_keys = frozenset(
            {
                "book_id",
                "chapter_index",
                "writing_basis_id",
                "understanding_id",
                "writing_plan_id",
                "requirement_ids",
                "outline_constraint_ids",
                "plan_json",
                "intent_json",
                "impact_map",
                "legacy_user_material",
            }
        )
        out = {k: v for k, v in snap.items() if k in allow or k in meta_keys}
        # Outline: drop manuscript blocks unless contract permits short hints
        if stage == "outline":
            contract = snap.get("outline_contract") if isinstance(snap.get("outline_contract"), dict) else {}
            if contract.get("manuscript_policy") != "structure_hint_only":
                out["source_manuscript_blocks"] = []
            else:
                out["source_manuscript_blocks"] = [
                    str(x)[:1500] for x in (snap.get("source_manuscript_blocks") or [])[:2]
                ]
        else:
            out.pop("source_outline_blocks", None)
            out.pop("source_reference_outline_blocks", None)
            out.pop("source_manuscript_blocks", None)
            out.pop("outline_contract", None)
        return out

    def _with_source_items(self, snap: dict, source_items: list[dict] | None) -> dict:
        snap["source_items"] = list(source_items or [])
        return snap

    def build_for_outline(self, book_id: UUID, *, source_items: list[dict] | None = None) -> dict:
        snap = self.apply_stage_whitelist(
            self._with_source_items(self.build_snapshot(book_id), source_items), "outline"
        )
        self.persist_snapshot(book_id, "outline", snap)
        return snap

    def build_for_narrative(self, book_id: UUID, *, source_items: list[dict] | None = None) -> dict:
        snap = self.apply_stage_whitelist(
            self._with_source_items(self.build_snapshot(book_id), source_items), "narrative"
        )
        self.persist_snapshot(book_id, "narrative", snap)
        return snap

    def build_for_chapter(
        self,
        book_id: UUID,
        chapter_index: int,
        *,
        source_items: list[dict] | None = None,
    ) -> dict:
        snap = self.apply_stage_whitelist(
            self._with_source_items(
                self.build_snapshot(book_id, chapter_index=chapter_index), source_items
            ),
            "chapter",
        )
        self.persist_snapshot(book_id, "chapter", snap)
        return snap

    def build_for_review(self, book_id: UUID, *, source_items: list[dict] | None = None) -> dict:
        snap = self.apply_stage_whitelist(
            self._with_source_items(self.build_snapshot(book_id), source_items), "review"
        )
        self.persist_snapshot(book_id, "review", snap)
        return snap

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
