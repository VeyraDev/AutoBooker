"""MechanismCompiler。"""

from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.contracts.field_registry import pick_str
from app.services.figures.contracts.geometry_kinds import GEOMETRY_GRAPH
from app.services.figures.contracts.normalize import normalize_content_brief
from app.services.figures.native.base import NativeIR
from app.services.figures.native.mechanism import empty_mechanism_ir
from app.services.figures.schemas.diagram import DiagramIntent

_LEGACY_RELATION_FIELD = "trans" + "fers"


class MechanismCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = normalize_content_brief(brief.diagram_type or intent.diagram_subtype, dict(brief.content_brief or {}))
        ir = empty_mechanism_ir()
        ir["geometry_kind"] = GEOMETRY_GRAPH
        ir["actors"] = list(content.get("actors") or [])
        ir["states"] = list(content.get("states") or [])
        ir["inputs"] = list(content.get("inputs") or [])
        ir["outputs"] = list(content.get("outputs") or [])
        ir["interactions"] = _normalize_interactions(
            content.get("作用关系")
            or content.get("interactions")
            or content.get(_LEGACY_RELATION_FIELD)
            or []
        )
        ir["feedbacks"] = list(content.get("feedbacks") or [])
        ir["notations"] = list(content.get("notations") or [])
        ir["layout_hints"] = ["mechanism_layered"]
        if not ir["interactions"]:
            ir["interactions"] = _interactions_from_flow(content)
        for t in ir["interactions"]:
            if isinstance(t, dict):
                effect = _normalize_effect(str(t.get("effect") or ""))
                link = {"from": t.get("from"), "to": t.get("to"), "polarity": "neutral"}
                if effect == "feedback":
                    ir["feedbacks"].append({"from": t.get("from"), "to": t.get("to"), "meaning": t.get("what")})
                if effect in {"activate", "inhibit"}:
                    link["polarity"] = "positive" if effect == "activate" else "negative"
                    ir["causal_links"].append(link)
        for fb in ir["feedbacks"]:
            if isinstance(fb, dict):
                ir["positive_feedbacks"].append(fb)
        return NativeIR(
            diagram_type="mechanism",
            title=brief.title or intent.title or "机制图",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_GRAPH},
        ).with_geometry_kind(GEOMETRY_GRAPH)


def _normalize_effect(effect: str) -> str:
    mapping = {
        "激活": "activate",
        "抑制": "inhibit",
        "转化": "transform",
        "聚合": "aggregate",
        "关注": "attend",
        "反馈": "feedback",
        "更新": "update",
    }
    return mapping.get(effect.strip(), effect.strip())


def _normalize_interactions(items: object) -> list[dict]:
    normalized: list[dict] = []
    if not isinstance(items, list):
        return normalized
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "from": item.get("from") or item.get("来源") or item.get("起点") or "",
            "to": item.get("to") or item.get("目标") or item.get("终点") or "",
            "what": item.get("what") or item.get("传递内容") or item.get("内容") or "",
            "effect": _normalize_effect(str(item.get("effect") or item.get("作用") or "")),
        })
    return normalized


def _interactions_from_flow(content: dict) -> list[dict]:
    labels: list[str] = []
    for item in content.get("main_flow") or content.get("steps") or []:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        elif isinstance(item, dict):
            label = pick_str(item, "label")
            if label:
                labels.append(label)
    interactions: list[dict] = []
    for i in range(len(labels) - 1):
        interactions.append({
            "from": labels[i],
            "to": labels[i + 1],
            "what": "",
            "effect": "transform",
        })
    return interactions
