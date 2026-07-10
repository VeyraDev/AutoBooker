"""Intake flow services."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.models.book import Book
from app.models.intake import (
    CreationOrigin,
    InputUnderstanding,
    IntakeItem,
    IntakeItemStatus,
    IntakeItemType,
    IntakeStatus,
    ProjectIntake,
    UnderstandingStatus,
    WritingPlan,
    WritingPlanStatus,
)
from app.models.material import MaterialTerm, OutlineConstraint, WritingRequirement
from app.services.writing.writing_context_builder import WritingContextBuilder
from app.utils.json_llm import parse_llm_json


_IMPACT_STAGES = ("outline", "narrative", "chapters", "review")
_TEMPLATE_PREFIXES = ("【当前理解】", "【写作方案】", "### 当前理解", "### 写作方案")
_INTAKE_ROLE_OPTIONS = {"outline", "reference", "style_sample", "negative_constraint", "goal"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _require_user_text(data: dict[str, Any], *, artifact: str) -> str:
    text = str(data.get("user_facing_text") or "").strip()
    if not text or text == "...":
        raise ValueError(f"{artifact} missing user_facing_text")
    if text.startswith(_TEMPLATE_PREFIXES):
        raise ValueError(f"{artifact} user_facing_text must not use a fixed heading template")
    return text


def _normalize_intent_json(data: dict[str, Any]) -> dict[str, Any]:
    intent = _as_dict(data.get("intent_json"))
    effects = _as_list(intent.get("must_influence"))
    if not intent or not effects:
        raise ValueError("input understanding must include LLM intent_json.must_influence")
    intent["must_influence"] = effects[:20]
    return intent


def _summary_with_intent(data: dict[str, Any]) -> dict[str, Any]:
    summary = dict(_as_dict(data.get("summary_json")))
    summary["intent_json"] = _normalize_intent_json(data)
    return summary


def _normalize_impact_map(data: dict[str, Any], intent_json: dict[str, Any]) -> dict[str, Any]:
    raw = _as_dict(data.get("impact_map"))
    if not raw:
        raise ValueError("writing plan must include impact_map")
    impact = dict(raw)
    for stage in _IMPACT_STAGES:
        impact[stage] = bool(raw.get(stage, True))
    if not any(impact[stage] for stage in _IMPACT_STAGES):
        raise ValueError("writing plan impact_map must affect at least one downstream stage")
    if not isinstance(impact.get("input_effects"), list):
        impact["input_effects"] = _as_list(intent_json.get("must_influence"))
    return impact


class OriginService:
    @staticmethod
    def normalize(origin: str) -> CreationOrigin:
        return CreationOrigin(origin)


class IntakeItemService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_intake(self, book: Book, origin: CreationOrigin) -> ProjectIntake:
        intake = (
            self.db.query(ProjectIntake)
            .filter(ProjectIntake.book_id == book.id, ProjectIntake.status != IntakeStatus.superseded)
            .order_by(ProjectIntake.created_at.desc())
            .first()
        )
        if intake:
            return intake
        intake = ProjectIntake(book_id=book.id, creation_origin=origin, status=IntakeStatus.collecting)
        self.db.add(intake)
        self.db.flush()
        return intake

    def add_text_item(self, intake: ProjectIntake, text: str, item_type: IntakeItemType) -> IntakeItem:
        item = IntakeItem(intake_id=intake.id, item_type=item_type, text_content=text, status=IntakeItemStatus.parsed)
        self.db.add(item)
        self.db.flush()
        return item

    def add_upload_item(
        self,
        intake: ProjectIntake,
        *,
        filename: str,
        content: bytes,
        owner_user_id,
        mime_type: str | None = None,
    ) -> IntakeItem:
        from app.models.binary_asset import AssetDomain, AssetRole
        from app.services.assets.binary_asset_service import BinaryAssetService

        asset = BinaryAssetService(self.db).create_asset(
            book_id=intake.book_id,
            owner_user_id=owner_user_id,
            content=content,
            filename=filename,
            mime_type=mime_type,
            asset_domain=AssetDomain.reference,
            asset_role=AssetRole.original_upload,
        )
        preview = ""
        if filename.lower().endswith(".txt") or (mime_type or "").startswith("text/"):
            preview = content.decode("utf-8", errors="replace")[:8000]
        elif filename.lower().endswith(".md"):
            preview = content.decode("utf-8", errors="replace")[:8000]
        item = IntakeItem(
            intake_id=intake.id,
            item_type=IntakeItemType.upload,
            filename=filename,
            text_content=preview or "[上传文件，暂未提取到可用于意图识别的正文]",
            asset_id=asset.id,
            parsed_preview=preview[:4000] if preview else None,
            status=IntakeItemStatus.parsed,
            detected_roles=[],
        )
        self.db.add(item)
        self.db.flush()
        if preview.strip():
            self._detect_roles(item, preview)
        return item

    def _detect_roles(self, item: IntakeItem, sample: str) -> None:
        sample = str(sample or "").strip()
        if not sample:
            item.detected_roles = []
            self.db.flush()
            return
        prompt = f"""根据材料内容（非文件名）判断其在书稿项目中的可能角色，可多选。
材料摘录：
{sample[:6000]}

输出 JSON：{{"detected_roles":["outline","reference","style_sample","negative_constraint","goal"]}}"""
        try:
            out = LLMClient().chat_completion(
                [{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.2,
            )
            data = parse_llm_json(out)
            roles = data.get("detected_roles") or []
            if isinstance(roles, list):
                item.detected_roles = [str(r) for r in roles if str(r) in _INTAKE_ROLE_OPTIONS][:8]
        except Exception:
            item.detected_roles = []
        self.db.flush()


class InputUnderstandingService:
    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMClient()

    def generate(self, book: Book, intake: ProjectIntake) -> InputUnderstanding:
        items = self.db.query(IntakeItem).filter(IntakeItem.intake_id == intake.id).all()
        materials = []
        for it in items:
            if it.item_type == IntakeItemType.upload:
                if it.parsed_preview:
                    materials.append({"type": "upload_preview", "text": it.parsed_preview[:4000]})
                else:
                    materials.append(
                        {
                            "type": "upload_unreadable",
                            "text": "用户上传了一个暂未提取到正文的文件；不要根据文件名或扩展名推断用途。",
                        }
                    )
                continue
            if it.text_content:
                materials.append({"type": it.item_type.value, "text": it.text_content[:8000]})
        prompt = f"""你是书稿策划编辑。必须通过 LLM 语义判断用户真实创作意图，不允许用关键词或固定规则解析。
根据用户输入生成自然语言「当前理解」，并给出后续写作必须受其影响的意图契约。
创作起点：{intake.creation_origin.value}
用户目标：{intake.raw_goal_text or "未说明"}
用户禁止事项：{intake.negative_constraints_text or "无"}
书名：{book.title}
材料：{json.dumps(materials, ensure_ascii=False)[:12000]}

输出 JSON：
{{
  "user_facing_text": "给用户看的自然语言理解。不要使用固定标题、编号模板或机械栏目，要像编辑对用户复述理解一样表达。",
  "summary_json": {{"book_goal":"","target_readers":"","scope":"","depth":""}},
  "intent_json": {{
    "primary_intent": "idea_only|material_first|outline_first|manuscript_continue|mixed|other",
    "book_promise": "这本书承诺帮读者获得什么",
    "reader_outcome": "读完后读者应能做什么或理解什么",
    "source_usage_intent": "用户材料应该如何进入大纲和正文",
    "must_influence": [
      {{"input_ref":"来自哪条用户输入或材料","writing_effect":"它必须怎样改变大纲/写作/审校","applies_to":["outline","chapters","review"],"strength":"must"}}
    ],
    "risk_controls": ["会影响理解或审校质量的风险控制"],
    "unknowns": ["仍需用户确认的问题"]
  }},
  "evidence_refs": [{{"source":"user_text","excerpt":"..."}}],
  "preserve_rules": [],
  "editable_rules": [],
  "avoid_rules": [],
  "unclear_questions": []
}}"""
        out = self.llm.chat_completion(
            [{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": prompt}],
            max_tokens=2500,
            temperature=0.3,
        )
        data = parse_llm_json(out)
        summary_json = _summary_with_intent(data)
        user_text = _require_user_text(data, artifact="input understanding")
        version = (
            self.db.query(InputUnderstanding)
            .filter(InputUnderstanding.intake_id == intake.id)
            .count()
            + 1
        )
        understanding = InputUnderstanding(
            book_id=book.id,
            intake_id=intake.id,
            version=version,
            summary_json=summary_json,
            user_facing_text=user_text,
            evidence_refs=data.get("evidence_refs"),
            preserve_rules=data.get("preserve_rules"),
            editable_rules=data.get("editable_rules"),
            avoid_rules=data.get("avoid_rules"),
            unclear_questions=data.get("unclear_questions"),
            status=UnderstandingStatus.draft,
        )
        self.db.add(understanding)
        intake.status = IntakeStatus.understanding_ready
        self.db.flush()
        return understanding

    def apply_user_correction(self, understanding: InputUnderstanding, correction: str) -> InputUnderstanding:
        book = self.db.query(Book).filter(Book.id == understanding.book_id).first()
        intake = self.db.query(ProjectIntake).filter(ProjectIntake.id == understanding.intake_id).first()
        if not book or not intake:
            raise ValueError("intake context missing")
        prompt = f"""用户在确认输入理解时提出修正：{correction}

上一版理解：
{understanding.user_facing_text}

上一版意图契约：
{json.dumps(_as_dict(understanding.summary_json).get("intent_json") or {}, ensure_ascii=False)[:4000]}

请重新生成 JSON（字段同前，必须重新给出 intent_json.must_influence）：user_facing_text, summary_json, intent_json, evidence_refs, preserve_rules, editable_rules, avoid_rules, unclear_questions"""
        out = self.llm.chat_completion(
            [{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": prompt}],
            max_tokens=2500,
            temperature=0.3,
        )
        data = parse_llm_json(out)
        summary_json = _summary_with_intent(data)
        user_text = _require_user_text(data, artifact="input understanding correction")
        understanding.status = UnderstandingStatus.superseded
        new_u = InputUnderstanding(
            book_id=book.id,
            intake_id=intake.id,
            version=understanding.version + 1,
            summary_json=summary_json,
            user_facing_text=user_text,
            evidence_refs=data.get("evidence_refs"),
            preserve_rules=data.get("preserve_rules"),
            editable_rules=data.get("editable_rules"),
            avoid_rules=data.get("avoid_rules"),
            unclear_questions=data.get("unclear_questions"),
            status=UnderstandingStatus.draft,
        )
        self.db.add(new_u)
        self.db.flush()
        return new_u


class WritingPlanService:
    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMClient()

    def generate(self, book: Book, intake: ProjectIntake, understanding: InputUnderstanding) -> WritingPlan:
        summary = _as_dict(understanding.summary_json)
        intent_json = _as_dict(summary.get("intent_json"))
        prompt = f"""基于已确认理解和 LLM 意图识别，生成简短写作方案/写作规则（给用户看的文字必须自然表达，不套固定模板）。

当前理解：
{understanding.user_facing_text}

意图契约：
{json.dumps(intent_json, ensure_ascii=False)[:6000]}

输出 JSON：
{{
  "user_facing_text": "...",
  "plan_json": {{"direction":"","audience":"","content_boundary":"","depth":"","voice":"","material_policy":[],"must_keep":[],"must_avoid":[]}},
  "impact_map": {{
    "outline": true,
    "narrative": true,
    "chapters": true,
    "review": true,
    "input_effects": [
      {{"input_ref":"来自哪条用户输入或材料","writing_effect":"会如何影响后续产物","applies_to":["outline","chapters","review"],"strength":"must"}}
    ],
    "quality_notes": ["会影响审校和输入理解质量的明确设计取舍"]
  }}
}}"""
        out = self.llm.chat_completion(
            [{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )
        data = parse_llm_json(out)
        user_text = _require_user_text(data, artifact="writing plan")
        impact_map = _normalize_impact_map(data, intent_json)
        version = self.db.query(WritingPlan).filter(WritingPlan.intake_id == intake.id).count() + 1
        plan = WritingPlan(
            book_id=book.id,
            intake_id=intake.id,
            understanding_id=understanding.id,
            version=version,
            plan_json=data.get("plan_json"),
            user_facing_text=user_text,
            impact_map=impact_map,
            status=WritingPlanStatus.draft,
        )
        self.db.add(plan)
        self.db.flush()
        return plan
class ConstraintSink:
    def __init__(self, db: Session):
        self.db = db

    def _deactivate_intake_material(self, book_id) -> None:
        self.db.query(WritingRequirement).filter(
            WritingRequirement.book_id == book_id,
            WritingRequirement.category.in_(
                (
                    "intake_must_keep",
                    "intake_must_avoid",
                    "intake_material_policy",
                    "intake_intent_effect",
                )
            ),
        ).update({"active": False})
        self.db.query(MaterialTerm).filter(
            MaterialTerm.book_id == book_id,
            MaterialTerm.term_type == "intake",
        ).update({"active": False})

    def confirm_plan(self, book: Book, intake: ProjectIntake, plan: WritingPlan, understanding: InputUnderstanding) -> None:
        plan.status = WritingPlanStatus.confirmed
        understanding.status = UnderstandingStatus.confirmed
        intake.confirmed_understanding_id = understanding.id
        intake.confirmed_writing_plan_id = plan.id
        intake.status = IntakeStatus.confirmed
        plan_json = plan.plan_json if isinstance(plan.plan_json, dict) else {}
        if plan_json.get("audience"):
            book.target_audience = str(plan_json["audience"])[:500]
        if plan_json.get("direction"):
            book.topic_brief = str(plan_json["direction"])[:20000]
        summary = understanding.summary_json if isinstance(understanding.summary_json, dict) else {}
        intent_json = summary.get("intent_json") if isinstance(summary.get("intent_json"), dict) else {}
        impact_map = plan.impact_map if isinstance(plan.impact_map, dict) else {}

        self._deactivate_intake_material(book.id)

        def _add_req(content: str, category: str, strength: str = "must") -> None:
            if not content.strip():
                return
            self.db.add(
                WritingRequirement(
                    book_id=book.id,
                    source_file_id=None,
                    content=content.strip()[:2000],
                    category=category,
                    strength=strength,
                    scope="book",
                    active=True,
                )
            )

        for item in plan_json.get("must_keep") or []:
            _add_req(str(item), "intake_must_keep", "must")
        for item in plan_json.get("must_avoid") or []:
            _add_req(str(item), "intake_must_avoid", "must")
        for item in plan_json.get("material_policy") or []:
            _add_req(str(item), "intake_material_policy", "should")
        for item in understanding.avoid_rules or []:
            _add_req(str(item), "intake_must_avoid", "must")
        for item in understanding.preserve_rules or []:
            _add_req(str(item), "intake_must_keep", "must")
        for item in (intent_json.get("must_influence") or []):
            if isinstance(item, dict):
                content = item.get("writing_effect") or item.get("input_ref") or ""
                strength = str(item.get("strength") or "must")
            else:
                content = str(item)
                strength = "must"
            _add_req(str(content), "intake_intent_effect", strength)
        for item in (impact_map.get("input_effects") or []):
            if isinstance(item, dict):
                content = item.get("writing_effect") or item.get("input_ref") or ""
                strength = str(item.get("strength") or "must")
            else:
                content = str(item)
                strength = "must"
            _add_req(str(content), "intake_intent_effect", strength)

        for key in ("book_goal", "target_readers", "scope", "depth"):
            val = summary.get(key)
            if val:
                self.db.add(
                    MaterialTerm(
                        book_id=book.id,
                        source_file_id=None,
                        term=str(val)[:300],
                        term_type="intake",
                        active=True,
                    )
                )

        WritingContextBuilder(self.db).persist_snapshot(
            book.id,
            "intake_confirm",
            WritingContextBuilder(self.db).build_snapshot(book.id),
        )
        self.db.flush()
