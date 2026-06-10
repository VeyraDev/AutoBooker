"""数据图解析。"""

from __future__ import annotations

import re

_GENERIC_NUMERIC_PAIR = re.compile(
    r"([A-Za-z][A-Za-z0-9._+/\-]{1,32})\s*[^\dA-Za-z]{0,8}\s*(\d+(?:\.\d+)?)\s*(?:ms|s|%|mb|gb)?",
    re.I,
)

from app.services.figures.parse.llm_helpers import call_llm_json, llm_available
from app.services.figure_render.renderer_rules import has_numeric_data_signal
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PCT_PAIR = re.compile(r"([^，,；;\s%]{1,20}?)(?:占|为)?\s*(\d+(?:\.\d+)?)\s*%")
_SCORE_PAIR = re.compile(r"([^，,；;：:\s]{1,24}?)(?:得分|为)\s*(\d+(?:\.\d+)?)\s*%?")

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
    default = {"chart_type": "bar", "title": intent.title, "labels": [], "values": []}
    # Hard gate: data_visualization must not be fabricated by the LLM.
    if not has_numeric_data_signal(ctx.normalized_input):
        return ParsedDiagram(default, "empty_chart_no_numeric_signal")
    if llm_available(ctx):
        try:
            data = call_llm_json(ctx, _PROMPT, max_tokens=1024, temperature=0.0)
            if isinstance(data, dict) and data.get("values"):
                return ParsedDiagram(data, "llm_chart")
        except Exception:
            pass
    return ParsedDiagram(default, "empty_chart")


def _infer_chart_type(text: str) -> str:
    t = text.lower()
    if re.search(r"饼图|份额|占比|市场份额", text):
        return "pie"
    if re.search(r"折线|曲线|趋势|loss", text, re.I):
        return "line"
    if re.search(r"散点", text):
        return "scatter"
    if re.search(r"热力", text):
        return "heatmap"
    if "bar" in t or "柱状" in text:
        return "bar"
    return "bar"


def parse_chart_data_rules(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    """从正文规则抽取 labels/values（无需 LLM）。"""
    text = ctx.normalized_input or ""
    chart_type = _infer_chart_type(text)
    labels: list[str] = []
    values: list[float] = []

    for pattern in (_PCT_PAIR, _SCORE_PAIR):
        for match in pattern.finditer(text):
            label = match.group(1).strip(" ：:，,。\"'（(")
            if not label or len(label) > 24:
                continue
            try:
                val = float(match.group(2))
            except ValueError:
                continue
            if label in labels:
                continue
            labels.append(label)
            values.append(val)

    if not values:
        for match in _GENERIC_NUMERIC_PAIR.finditer(text):
            label = match.group(1).strip(" .,:;()[]{}")
            if not label or label.lower() in {"ms", "sec", "api"}:
                continue
            try:
                val = float(match.group(2))
            except ValueError:
                continue
            if label in labels:
                continue
            labels.append(label)
            values.append(val)

    if not values:
        return ParsedDiagram(
            {"chart_type": chart_type, "title": intent.title, "labels": [], "values": []},
            "empty_chart_rules",
        )

    return ParsedDiagram(
        {
            "chart_type": chart_type,
            "title": intent.title,
            "labels": labels,
            "values": values,
            "x_label": "",
            "y_label": "ms" if "ms" in text.lower() else "",
        },
        "rules_chart",
    )


def chart_brief_to_spec(chart_brief: dict) -> dict:
    """Chart Brief → Matplotlib spec。"""
    if not isinstance(chart_brief, dict):
        return {}
    labels = [str(x) for x in (chart_brief.get("labels") or chart_brief.get("categories") or [])]
    values: list[float] = []
    for item in chart_brief.get("values") or chart_brief.get("data_points") or []:
        if isinstance(item, dict):
            try:
                values.append(float(item.get("value") or item.get("y") or 0))
            except (TypeError, ValueError):
                continue
        else:
            try:
                values.append(float(item))
            except (TypeError, ValueError):
                continue
    y_metrics = chart_brief.get("y_metrics") or []
    if not values and y_metrics:
        for m in y_metrics:
            if isinstance(m, dict) and m.get("values"):
                values.extend(float(v) for v in m["values"] if v is not None)
    return {
        "chart_type": chart_brief.get("chart_type") or "bar",
        "title": chart_brief.get("title") or "",
        "labels": labels,
        "values": values,
        "x_label": (chart_brief.get("x_dimension") or {}).get("name", "") if isinstance(chart_brief.get("x_dimension"), dict) else "",
        "y_label": y_metrics[0].get("name", "") if y_metrics and isinstance(y_metrics[0], dict) else "",
    }
