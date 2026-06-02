"""决策树解析。"""

from __future__ import annotations

from app.config import settings
from app.llm.client import LLMClient
from app.services.figure_render.figure_structure import infer_structured_spec
from app.services.figures.parse.generic_graph import parse_generic_graph
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析决策树 JSON：
{{
  "root": "根问题",
  "branches": [{{"label":"需求/条件","target":"方案名","tags":["优势词"]}}]
}}
层数可变：若有「条件→选择→优势」则 branches 含 tags；仅「条件→选择」则 tags 可空。
只输出 JSON。描述：{text}
"""


def _branches_to_graph(data: dict) -> dict:
    root = str(data.get("root") or data.get("root_question") or "根节点").strip()
    branches = data.get("branches") or []
    nodes = [{"id": "root", "label": root, "shape": "diamond", "level": 0, "column": 0}]
    edges: list[dict] = []
    for i, br in enumerate(branches[:6]):
        if not isinstance(br, dict):
            continue
        label = str(br.get("label") or br.get("condition") or "").strip()
        target = str(br.get("target") or br.get("choice") or "").strip()
        tags = br.get("tags") or br.get("benefit_tags") or []
        cid, nid = f"c{i}", f"n{i}"
        if label:
            nodes.append({"id": cid, "label": label[:36], "shape": "box", "level": 1, "column": i})
            edges.append({"from": "root", "to": cid})
        if target:
            choice = target if target.startswith("选择") else f"选择 {target}"
            nodes.append({"id": nid, "label": choice[:28], "shape": "rounded", "level": 2, "column": i})
            edges.append({"from": cid if label else "root", "to": nid})
        if isinstance(tags, list):
            for j, tag in enumerate(tags[:6]):
                tid = f"t{i}_{j}"
                nodes.append({
                    "id": tid,
                    "label": str(tag)[:10],
                    "shape": "tag",
                    "level": 3,
                    "column": i,
                    "parent": nid,
                })
                edges.append({"from": nid, "to": tid})
    return {"layout": "TB", "structure_summary": "决策树", "nodes": nodes, "edges": edges}


def parse_decision_tree(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    model = (ctx.model or settings.intent_model).strip()
    if ctx.use_llm and model:
        try:
            out = LLMClient().chat_completion(
                [{"role": "user", "content": _PROMPT.format(text=ctx.normalized_input[:3000])}],
                model=model,
                max_tokens=2048,
                temperature=0.2,
            )
            data = parse_llm_json(out)
            if isinstance(data, dict) and data.get("branches"):
                spec = _branches_to_graph(data)
                if intent.title:
                    spec["title"] = intent.title
                return ParsedDiagram(spec, "llm_decision")
        except Exception:
            pass
    spec = infer_structured_spec(ctx.normalized_input)
    if spec:
        return ParsedDiagram(spec, "rules_decision")
    return parse_generic_graph(ctx, intent)
