"""SWOT 矩阵解析。"""

from __future__ import annotations

from app.services.figures.parse.llm_helpers import call_llm_json, llm_available
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析 SWOT 分析 JSON：
{{
  "title": "SWOT 分析",
  "strengths": ["..."],
  "weaknesses": ["..."],
  "opportunities": ["..."],
  "threats": ["..."]
}}
只输出 JSON。描述：{text}
"""


def parse_swot(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    default = {
        "title": intent.title or "SWOT 分析",
        "strengths": ["优势项"],
        "weaknesses": ["劣势项"],
        "opportunities": ["机会项"],
        "threats": ["威胁项"],
    }
    if llm_available(ctx):
        try:
            data = call_llm_json(ctx, _PROMPT, max_tokens=2048, temperature=0.2)
            if isinstance(data, dict):
                for k in ("strengths", "weaknesses", "opportunities", "threats"):
                    data.setdefault(k, default[k])
                data.setdefault("title", intent.title or "SWOT 分析")
                return ParsedDiagram(data, "llm_swot")
        except Exception:
            pass
    return ParsedDiagram(default, "default_swot")
