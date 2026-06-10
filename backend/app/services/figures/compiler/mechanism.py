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


class MechanismCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = normalize_content_brief(brief.diagram_type or intent.diagram_subtype, dict(brief.content_brief or {}))
        ir = empty_mechanism_ir()
        ir["geometry_kind"] = GEOMETRY_GRAPH
        ir["actors"] = list(content.get("actors") or [])
        ir["states"] = list(content.get("states") or [])
        ir["inputs"] = list(content.get("inputs") or [])
        ir["outputs"] = list(content.get("outputs") or [])
        ir["transfers"] = list(content.get("transfers") or [])
        ir["feedbacks"] = list(content.get("feedbacks") or [])
        ir["notations"] = list(content.get("notations") or [])
        ir["layout_hints"] = ["mechanism_layered"]
        if not ir["transfers"]:
            ir["transfers"] = _transfers_from_flow(content)
        for t in ir["transfers"]:
            if isinstance(t, dict):
                effect = str(t.get("effect") or "")
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


def _transfers_from_flow(content: dict) -> list[dict]:
    labels: list[str] = []
    for item in content.get("main_flow") or content.get("steps") or []:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        elif isinstance(item, dict):
            label = pick_str(item, "label")
            if label:
                labels.append(label)
    transfers: list[dict] = []
    for i in range(len(labels) - 1):
        transfers.append({
            "from": labels[i],
            "to": labels[i + 1],
            "what": "",
            "effect": "transform",
        })
    return transfers
