"""数据图解析。"""

from __future__ import annotations

from app.config import settings
from app.llm.client import LLMClient
from app.services.figure_render.renderer_rules import has_numeric_data_signal
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """从描述中解析真实存在的图表数据 JSON。不得补造、估算、想象数据。

只输出 JSON：
{{
  "chart_type": "bar|line|pie|scatter",
  "title": "",
  "labels": [],
  "values": [],
  "x_label": "",
  "y_label": ""
}}

要求：
- 只能使用描述中明确给出的数字。
- 如果没有明确数字，labels 和 values 必须为空数组。
- values 必须是数字数组，不能写中文说明。

描述：{text}
"""


def parse_chart_data(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    model = (ctx.model or settings.intent_model).strip()
    default = {"chart_type": "bar", "title": intent.title, "labels": [], "values": []}
    # Hard gate: data_visualization must not be fabricated by the LLM.
    if not has_numeric_data_signal(ctx.normalized_input):
        return ParsedDiagram(default, "empty_chart_no_numeric_signal")
    if ctx.use_llm and model:
        try:
            out = LLMClient().chat_completion(
                [{"role": "user", "content": _PROMPT.format(text=ctx.normalized_input[:2500])}],
                model=model,
                max_tokens=1024,
                temperature=0.0,
            )
            data = parse_llm_json(out)
            if isinstance(data, dict) and data.get("values"):
                return ParsedDiagram(data, "llm_chart")
        except Exception:
            pass
    return ParsedDiagram(default, "empty_chart")
