"""通用 nodes/edges 结构解析。"""

from __future__ import annotations

from app.config import settings
from app.llm.client import LLMClient
from app.services.figure_render.figure_structure import infer_structured_spec
from app.services.figures.parse.fallback import parse_fallback
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PARSE_PROMPT = """将描述解析为图结构 JSON（层数由描述决定，禁止固定模板层数）：
{{
  "layout": "TB|LR",
  "structure_summary": "简述层数与语义",
  "nodes": [{{"id":"n1","label":"短标签","shape":"diamond|box|rounded|tag","level":0,"column":0,"parent":"可选"}}],
  "edges": [{{"from":"id","to":"id"}}]
}}
描述中每一语义层对应不同 level；「A→B」必须有边。只输出 JSON。
描述：{text}
"""


def parse_generic_graph(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    model = (ctx.model or settings.intent_model).strip()
    if ctx.use_llm and model:
        try:
            out = LLMClient().chat_completion(
                [{"role": "user", "content": _PARSE_PROMPT.format(text=ctx.normalized_input[:3000])}],
                model=model,
                max_tokens=4096,
                temperature=0.2,
            )
            data = parse_llm_json(out)
            if isinstance(data, dict) and data.get("nodes"):
                if intent.title and not data.get("title"):
                    data["title"] = intent.title
                return ParsedDiagram(data, "llm_generic")
        except Exception:
            pass
    spec = infer_structured_spec(ctx.normalized_input)
    if spec:
        return ParsedDiagram(spec, "rules_generic")
    return parse_fallback(ctx, intent)
