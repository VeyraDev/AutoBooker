"""V3 Chart Pipeline：Chart Brief → Data Validator → Matplotlib spec。"""

from __future__ import annotations

from typing import Any

from app.services.figures.brief.chart import extract_chart_brief
from app.services.figures.parse.chart_data import chart_brief_to_spec
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext, VisualPlan
from app.services.figures.validate.chart_data import validate_chart_brief


def run_chart_pipeline(
    ctx: PipelineContext,
    intent: DiagramIntent,
    understanding: dict[str, Any] | None = None,
) -> tuple[DiagramIntent, ParsedDiagram, VisualPlan | None, dict, list[str], dict[str, Any]]:
    quality_flags: list[str] = []
    ir_bundle: dict[str, Any] = {
        "intent_understanding": understanding or ctx.intent_understanding or {},
        "pipeline": "v3_chart",
    }

    intent = DiagramIntent(
        "data",
        "chart",
        max(intent.confidence, 0.85),
        intent.source + "+v3_chart",
        intent.title,
        diagram_type="chart",
        reason=intent.reason or "数据图 V3 管线",
        fallback_allowed=intent.fallback_allowed,
    )

    brief_payload = extract_chart_brief(ctx, ir_bundle["intent_understanding"])
    brief_payload, val_warnings = validate_chart_brief(brief_payload)
    quality_flags.extend(val_warnings)
    ir_bundle["chart_brief"] = brief_payload

    spec: dict[str, Any] = {}
    if str(brief_payload.get("chart_status")) == "ready":
        spec = chart_brief_to_spec(brief_payload.get("chart_brief") or {})
    if not spec:
        from app.services.figures.parse.chart_data import parse_chart_data_rules

        rule_parsed = parse_chart_data_rules(ctx, intent)
        spec = dict(rule_parsed.parsed_spec or {})
        if spec.get("values") or spec.get("series"):
            quality_flags.append("chart_data_rule_extracted")

    spec["diagram_subtype"] = "chart"
    spec["render_mode"] = "structured_chart"
    spec["layout_strategy"] = "chart"
    spec["title"] = spec.get("title") or intent.title or "数据图"
    has_chart_data = bool(spec.get("values") or spec.get("series") or spec.get("data"))
    if str(brief_payload.get("chart_status")) == "need_data" and not has_chart_data:
        spec["render_mode"] = "need_data"
        quality_flags.append("chart_missing_numeric_data")
    elif str(brief_payload.get("chart_status")) == "need_data" and has_chart_data:
        quality_flags.append("chart_data_rule_recovered")

    parsed = ParsedDiagram(spec, "v3_chart")
    visual = VisualPlan(
        layout="chart",
        style="data visualization; clean axes; publication aspect ratio 4:3",
        visual_description=ctx.normalized_input[:400],
        must_include=["坐标轴", "数据标签"],
        must_avoid=["装饰性插画"],
    )
    return intent, parsed, visual, spec, quality_flags, ir_bundle
