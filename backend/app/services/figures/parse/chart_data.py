"""数据图解析。"""

from __future__ import annotations

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析图表数据 JSON：
{{
  "chart_type": "bar|line|pie|scatter",
  "title": "",
  "labels": [],
  "values": []
}}
只输出 JSON。描述：{text}
"""


def parse_chart_data(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    model = (ctx.model or settings.intent_model).strip()
    if ctx.use_llm and model:
        try:
            out = LLMClient().chat_completion(
                [{"role": "user", "content": _PROMPT.format(text=ctx.normalized_input[:2500])}],
                model=model,
                max_tokens=1024,
                temperature=0.2,
            )
            data = parse_llm_json(out)
            if isinstance(data, dict) and data.get("values"):
                return ParsedDiagram(data, "llm_chart")
        except Exception:
            pass
    return ParsedDiagram({"chart_type": "bar", "title": intent.title, "labels": [], "values": []}, "empty_chart")
