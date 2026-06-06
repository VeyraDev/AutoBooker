"""调用 A：语义解构 — entities/relations/groups/notes。"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_VERB_IN_NAME_RE = re.compile(r"连接|通知|调用|依赖|写入|读取|通过|包含|触发|异步|同步")
_ENTITY_TYPE_MAP = {
    "service": "service",
    "api": "gateway",
    "gateway": "gateway",
    "user": "user",
    "data": "database",
    "database": "database",
    "process": "process",
    "decision": "decision",
    "external": "external",
    "group": "module",
    "queue": "queue",
    "module": "module",
}

_DIAGRAM_TYPE_MAP = {
    "flow": "flowchart",
    "architecture": "architecture",
    "comparison": "comparison",
    "tree": "taxonomy",
    "timeline": "timeline",
    "network": "architecture",
    "infographic": "taxonomy",
}


def call_semantic_plan(ctx: PipelineContext, intent: DiagramIntent) -> dict[str, Any] | None:
    """调用 A：LLM 语义解构，返回 semantic dict 或 None。"""
    model = (ctx.model or settings.intent_model).strip()
    if not ctx.use_llm or not model or not ctx.normalized_input.strip():
        return None
    diagram_type = intent.diagram_type or "flowchart"
    layout_lines = "\n".join(f"- {x}" for x in (ctx.layout_instructions or [])) or "（无）"
    try:
        prompt = format_prompt(
            "semantic",
            book_type=ctx.book_type or "nonfiction",
            diagram_type=diagram_type,
            text=ctx.normalized_input[:3500],
            layout_instructions=layout_lines,
        )
    except OSError:
        return None
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=1500,
            temperature=0.0,
        )
        data = parse_llm_json(out)
    except Exception as e:
        logger.warning("semantic plan LLM failed: %s", e)
        return None
    if not isinstance(data, dict):
        return None
    return _normalize_semantic(data, intent)


def _normalize_semantic(data: dict[str, Any], intent: DiagramIntent) -> dict[str, Any]:
    raw_type = str(data.get("diagram_type") or "flow").strip().lower()
    diagram_type = _DIAGRAM_TYPE_MAP.get(raw_type, intent.diagram_type or "flowchart")
    title = str(data.get("title") or intent.title or "").strip()[:24]

    entities: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for i, ent in enumerate(data.get("entities") or []):
        if not isinstance(ent, dict):
            continue
        eid = str(ent.get("id") or f"e{i + 1}").strip()
        if eid in seen_ids:
            eid = f"e{i + 1}"
        seen_ids.add(eid)
        raw_t = str(ent.get("type") or "process").strip().lower()
        name = str(ent.get("name") or "").strip()[:16]
        etype = _ENTITY_TYPE_MAP.get(raw_t, "process")
        if re.fullmatch(r"(不达标|未达标|达标)", name):
            name = "是否达标"
            etype = "decision"
        elif name.startswith("是否") or re.search(r"判断|达标", name):
            etype = "decision"
        entities.append({
            "id": eid,
            "name": name,
            "type": etype,
        })

    relations: list[dict[str, Any]] = []
    for rel in data.get("relations") or []:
        if not isinstance(rel, dict):
            continue
        relations.append({
            "from": str(rel.get("from") or "").strip(),
            "to": str(rel.get("to") or "").strip(),
            "verb": str(rel.get("verb") or "").strip()[:8],
            "async": bool(rel.get("async", False)),
            "label": str(rel.get("label") or "").strip()[:12],
        })

    groups: list[dict[str, Any]] = []
    for gi, grp in enumerate(data.get("groups") or []):
        if not isinstance(grp, dict):
            continue
        members = [str(m).strip() for m in (grp.get("members") or []) if str(m).strip()]
        groups.append({
            "id": str(grp.get("id") or f"g{gi + 1}").strip(),
            "label": str(grp.get("label") or "").strip(),
            "members": members,
        })

    notes = [str(n).strip() for n in (data.get("notes") or []) if str(n).strip()]

    return {
        "diagram_type": diagram_type,
        "title": title or intent.title or "示意图",
        "entities": entities,
        "relations": relations,
        "groups": groups,
        "notes": notes,
    }


def _validate_semantic(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """校验语义解构结果，必要时就地修复。"""
    warnings: list[str] = []
    entities = data.get("entities") or []
    if not isinstance(entities, list) or len(entities) < 2:
        return False, ["too_few_entities"]

    entity_ids = {str(e.get("id") or "") for e in entities if isinstance(e, dict)}
    entity_ids.discard("")

    valid_entities: list[dict[str, Any]] = []
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or "").strip()
        if not name:
            warnings.append("empty_entity_name")
            continue
        if _VERB_IN_NAME_RE.search(name):
            warnings.append(f"verb_in_entity_name:{name}")
        valid_entities.append(ent)

    if len(valid_entities) < 2:
        return False, warnings + ["too_few_valid_entities"]

    if len(valid_entities) > 16:
        warnings.append("entities_truncated")
        valid_entities = valid_entities[:16]
        entity_ids = {str(e.get("id") or "") for e in valid_entities}

    data["entities"] = valid_entities

    valid_relations: list[dict[str, Any]] = []
    for rel in data.get("relations") or []:
        if not isinstance(rel, dict):
            continue
        src = str(rel.get("from") or "").strip()
        dst = str(rel.get("to") or "").strip()
        if src not in entity_ids or dst not in entity_ids:
            warnings.append(f"invalid_relation:{src}->{dst}")
            continue
        if src == dst:
            continue
        valid_relations.append(rel)
    data["relations"] = valid_relations

    is_usable = len(valid_entities) >= 2 and not any(
        w.startswith("verb_in_entity_name:") for w in warnings
    )
    return is_usable, warnings


def parse_semantic_plan(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram | None:
    """兼容旧 registry 路径：语义解构成功时返回最小 ParsedDiagram。"""
    semantic = call_semantic_plan(ctx, intent)
    if not semantic:
        return None
    usable, _ = _validate_semantic(semantic)
    if not usable:
        return None
    spec = {
        "title": semantic.get("title"),
        "diagram_type": semantic.get("diagram_type"),
        "entities": semantic.get("entities"),
        "relations": semantic.get("relations"),
        "groups": semantic.get("groups"),
        "notes": semantic.get("notes"),
    }
    return ParsedDiagram(spec, "llm_semantic_deconstruct")


# --- 旧测试兼容 ---
def _normalize_plan(data: dict[str, Any], intent: DiagramIntent) -> dict[str, Any]:
    from app.services.figures.intent.taxonomy import canonical_subtype
    from app.services.figures.parse.hygiene import icon_hint

    spec = dict(data.get("spec") if isinstance(data.get("spec"), dict) else data)
    subtype = canonical_subtype(str(spec.get("diagram_subtype") or intent.diagram_subtype))
    spec["diagram_subtype"] = subtype
    spec["title"] = str(spec.get("title") or intent.title or "").strip()
    layout = str(spec.get("layout") or "").strip().upper()
    spec["layout"] = layout if layout in {"LR", "TB"} else "LR"
    stages = [s for s in spec.get("stages") or [] if isinstance(s, dict) and str(s.get("label") or "").strip()]
    if stages and not spec.get("nodes"):
        spec["nodes"] = [
            {
                "id": str(stage.get("id") or f"s{i}"),
                "label": str(stage.get("label") or ""),
                "shape": "diamond" if stage.get("kind") == "decision" else "rounded",
                "level": i,
                "column": 0,
                "icon": icon_hint(str(stage.get("label") or "")),
            }
            for i, stage in enumerate(stages)
        ]
    return spec
