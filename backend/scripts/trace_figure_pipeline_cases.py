"""Trace figure generation pipeline cases without external LLM calls.

The script reads tests/fixtures/figures/figure_type_pipeline_cases.json, runs each
case through the current V3 pipeline, records every important layer, and writes:

- tests/fixtures/figures/figure_type_pipeline_traces.json
- docs/图像生成逐层测试报告.md
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.figures.classification.resolver import build_classification_record
from app.services.figures.intent.resolve import intent_from_subtype_hint, resolve_intent_unified
from app.services.figures.intent.understand import understand_intent
from app.services.figures.pipeline.chart_run import run_chart_pipeline
from app.services.figures.pipeline.illustration_run import run_illustration_pipeline
from app.services.figures.pipeline.normalize import normalize_figure_input
from app.services.figures.pipeline.structured_run import run_structured_pipeline
from app.services.figures.pipeline.type_router import PipelineRoute, route_from_understanding
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext, VisualPlan

DEFAULT_CASES = BACKEND_ROOT / "tests" / "fixtures" / "figures" / "figure_type_pipeline_cases.json"
DEFAULT_TRACE = BACKEND_ROOT / "tests" / "fixtures" / "figures" / "figure_type_pipeline_traces.json"
DEFAULT_REPORT = WORKSPACE_ROOT / "docs" / "图像生成逐层测试报告.md"


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _intent_dict(intent: DiagramIntent) -> dict[str, Any]:
    return {
        "diagram_family": intent.diagram_family,
        "diagram_subtype": intent.diagram_subtype,
        "diagram_type": intent.diagram_type,
        "confidence": intent.confidence,
        "source": intent.source,
        "title": intent.title,
        "reason": intent.reason,
        "fallback_allowed": intent.fallback_allowed,
    }


def _spec_summary(spec: dict[str, Any] | None) -> dict[str, Any]:
    spec = spec if isinstance(spec, dict) else {}
    return {
        "diagram_subtype": spec.get("diagram_subtype"),
        "diagram_type": spec.get("diagram_type"),
        "render_mode": spec.get("render_mode"),
        "geometry_kind": spec.get("geometry_kind"),
        "layout_strategy": spec.get("layout_strategy") or spec.get("layout"),
        "render_profile": spec.get("render_profile"),
        "graph_visual_grammar": spec.get("graph_visual_grammar"),
        "matrix_visual_grammar": spec.get("matrix_visual_grammar"),
        "mandatory_semantics": spec.get("mandatory_semantics") or [],
        "visual_directives": spec.get("visual_directives") or [],
        "directive_ids": spec.get("directive_ids") or [],
        "node_count": len(spec.get("nodes") or []),
        "edge_count": len(spec.get("edges") or []),
        "event_count": len(spec.get("events") or []),
        "cell_count": len(spec.get("cells") or []),
        "block_count": len(spec.get("blocks") or []),
        "quality_flags": list(spec.get("quality_flags") or []),
    }


def _layout_summary(layout_result: dict[str, Any] | None) -> dict[str, Any]:
    layout_result = layout_result if isinstance(layout_result, dict) else {}
    return {
        "strategy": layout_result.get("strategy"),
        "direction": layout_result.get("direction"),
        "canvas": layout_result.get("canvas"),
        "node_position_count": len(layout_result.get("node_positions") or {}),
        "edge_route_count": len(layout_result.get("edge_routes") or []),
    }


def _record_summary(record: dict[str, Any] | None) -> dict[str, Any]:
    record = record if isinstance(record, dict) else {}
    return {
        "diagram_family": record.get("diagram_family"),
        "diagram_subtype": record.get("diagram_subtype"),
        "diagram_type": record.get("diagram_type"),
        "renderer": record.get("renderer"),
        "image_type": record.get("image_type"),
        "layout_strategy": record.get("layout_strategy"),
        "quality_flags": list(record.get("quality_flags") or []),
        "render_warnings": list(record.get("render_warnings") or []),
        "quality_report_status": (record.get("quality_report") or {}).get("status")
        if isinstance(record.get("quality_report"), dict)
        else None,
    }


def _run_route(
    *,
    ctx: PipelineContext,
    intent: DiagramIntent,
    understanding: dict[str, Any],
    route_value: str,
) -> dict[str, Any]:
    route = PipelineRoute(route_value)
    if route == PipelineRoute.CHART:
        final_intent, parsed, visual, dsl_json, quality_flags, ir_bundle = run_chart_pipeline(ctx, intent, understanding)
    elif route == PipelineRoute.ILLUSTRATION:
        final_intent, parsed, visual, dsl_json, quality_flags, ir_bundle = run_illustration_pipeline(ctx, intent, understanding)
    elif route == PipelineRoute.SCREENSHOT:
        parsed = ParsedDiagram({"title": intent.title, "render_mode": "screenshot_placeholder"}, source="trace_screenshot")
        final_intent, visual, dsl_json, quality_flags, ir_bundle = intent, None, {}, ["screenshot_placeholder"], {
            "intent_understanding": understanding,
            "pipeline": "trace_screenshot",
        }
    else:
        final_intent, parsed, visual, dsl_json, quality_flags, ir_bundle = run_structured_pipeline(
            ctx,
            intent,
            understanding=understanding,
        )

    ir_bundle = ir_bundle or {}
    ir_bundle.setdefault("intent_understanding", understanding)
    record = build_classification_record(
        ctx,
        final_intent,
        parsed,
        visual_plan=visual if isinstance(visual, VisualPlan) else None,
        dsl_json=dsl_json,
        ir_bundle=ir_bundle,
    ).to_json()
    parsed_spec = parsed.parsed_spec if isinstance(parsed, ParsedDiagram) else {}
    layout_result = ir_bundle.get("layout_result") or parsed_spec.get("layout_result")
    return {
        "route": route.value,
        "intent": _intent_dict(final_intent),
        "parsed_source": getattr(parsed, "source", ""),
        "parsed_spec_summary": _spec_summary(parsed_spec),
        "parsed_spec": _jsonable(parsed_spec),
        "visual_plan": _jsonable(visual),
        "dsl_json": _jsonable(dsl_json),
        "quality_flags": list(quality_flags or []),
        "ir_bundle": _jsonable(ir_bundle),
        "layout_summary": _layout_summary(layout_result),
        "classification_summary": _record_summary(record),
        "classification_record": _jsonable(record),
    }


def _evaluate_run(case: dict[str, Any], run: dict[str, Any] | None) -> dict[str, Any]:
    expected = case.get("expected") or {}
    failures: list[str] = []
    warnings: list[str] = []
    if not isinstance(run, dict) or run.get("error"):
        return {
            "status": "failed",
            "failures": ["pipeline_exception"],
            "warnings": [],
            "suspected_layers": ["pipeline_exception"],
            "degradations": [{"code": "pipeline_exception", "detail": (run or {}).get("error", "")}],
        }

    parsed = run.get("parsed_spec_summary") or {}
    cls = run.get("classification_summary") or {}
    actual = {
        "route": run.get("route"),
        "diagram_subtype": cls.get("diagram_subtype") or parsed.get("diagram_subtype") or (run.get("intent") or {}).get("diagram_subtype"),
        "renderer": cls.get("renderer"),
        "geometry_kind": parsed.get("geometry_kind"),
        "render_profile": parsed.get("render_profile"),
        "graph_visual_grammar": parsed.get("graph_visual_grammar"),
        "matrix_visual_grammar": parsed.get("matrix_visual_grammar"),
        "render_mode": parsed.get("render_mode"),
    }
    for key in (
        "route",
        "diagram_subtype",
        "renderer",
        "geometry_kind",
        "render_profile",
        "graph_visual_grammar",
        "render_mode",
    ):
        if key not in expected:
            continue
        if expected.get(key) != actual.get(key):
            failures.append(f"{key}_mismatch")

    parsed_spec = run.get("parsed_spec") or {}
    missing_fields = [
        field for field in (expected.get("required_spec_fields") or [])
        if not parsed_spec.get(field)
    ]
    if missing_fields:
        failures.append("required_fields_missing")

    quality_flags = list(parsed.get("quality_flags") or []) + list(cls.get("quality_flags") or [])
    if quality_flags:
        warnings.append("quality_flags_present")
    if cls.get("render_warnings"):
        warnings.append("render_warnings_present")

    degradations = [{"code": f, "detail": _detail_for_failure(f, expected, actual, missing_fields)} for f in failures]
    suspected_layers = _suspected_layers(
        case=case,
        run=run,
        failures=failures,
        warnings=warnings,
        missing_fields=missing_fields,
    )
    status = "failed" if failures else ("warning" if warnings else "passed")
    return {
        "status": status,
        "expected": expected,
        "actual": actual,
        "missing_required_fields": missing_fields,
        "failures": failures,
        "warnings": warnings,
        "suspected_layers": suspected_layers,
        "quality_flags": list(dict.fromkeys(quality_flags)),
        "degradations": degradations,
    }


def _detail_for_failure(
    code: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    missing_fields: list[str],
) -> str:
    if code == "required_fields_missing":
        return "missing " + ", ".join(missing_fields)
    key = code.removesuffix("_mismatch")
    return f"expected {expected.get(key)!r}, got {actual.get(key)!r}"


def _suspected_layers(
    *,
    case: dict[str, Any],
    run: dict[str, Any],
    failures: list[str],
    warnings: list[str],
    missing_fields: list[str],
) -> list[str]:
    """Best-effort diagnosis: which pipeline layer first lost the expected semantics."""
    layers: list[str] = []
    expected = case.get("expected") or {}
    spec = run.get("parsed_spec") if isinstance(run.get("parsed_spec"), dict) else {}
    parsed_summary = run.get("parsed_spec_summary") or {}
    ir_bundle = run.get("ir_bundle") if isinstance(run.get("ir_bundle"), dict) else {}
    visual_brief = ir_bundle.get("visual_brief") if isinstance(ir_bundle.get("visual_brief"), dict) else {}
    native_ir = ir_bundle.get("native_ir") if isinstance(ir_bundle.get("native_ir"), dict) else {}
    native_structure = native_ir.get("native_structure") if isinstance(native_ir.get("native_structure"), dict) else {}

    def add(layer: str) -> None:
        if layer not in layers:
            layers.append(layer)

    if "route_mismatch" in failures:
        add("type_router")
    if "render_mode_mismatch" in failures and expected.get("route") == "chart":
        add("chart_pipeline")
    if "render_mode_mismatch" in failures and expected.get("route") == "illustration":
        add("illustration_pipeline")
    if "diagram_subtype_mismatch" in failures:
        add("intent_resolution")
    if "geometry_kind_mismatch" in failures:
        add("compiler_registry/native_ir")
        add("geometry_projector")
    if "graph_visual_grammar_mismatch" in failures:
        add("render_spec/graph_visual_grammar")
    if "render_profile_mismatch" in failures:
        add("renderer_profile_selection")

    if missing_fields:
        content_brief = visual_brief.get("content_brief") if isinstance(visual_brief.get("content_brief"), dict) else {}
        if any(field in {"events", "children", "edges", "nodes", "cells", "blocks", "labels", "values"} for field in missing_fields):
            if not content_brief or all(not content_brief.get(field) for field in missing_fields):
                add("visual_brief/content_extraction")
            elif all(not native_structure.get(field) for field in missing_fields):
                add("compiler/native_ir")
            elif all(not spec.get(field) for field in missing_fields):
                add("render_spec_assembly")

    if "quality_flags_present" in warnings:
        flags = list(parsed_summary.get("quality_flags") or []) + list((run.get("classification_summary") or {}).get("quality_flags") or [])
        if "native_invalid" in flags:
            add("native_gate")
        if "design_violation" in flags:
            add("design_gate")
        if "semantic_dsl_misalignment" in flags:
            add("structural_critic")

    return layers or ["ok"]


def trace_case(case: dict[str, Any]) -> dict[str, Any]:
    prompt = str(case["prompt"])
    subtype_hint = str(case.get("subtype_hint") or "")
    normalized, layout_instructions = normalize_figure_input(prompt)
    ctx = PipelineContext(
        description=prompt,
        normalized_input=normalized,
        layout_instructions=layout_instructions,
        subtype_hint=subtype_hint,
        model="",
        use_llm=False,
    )
    understanding = understand_intent(ctx)
    actual_intent = resolve_intent_unified(ctx, understanding)
    actual_route = route_from_understanding(
        understanding,
        subtype_hint=ctx.subtype_hint or actual_intent.diagram_subtype,
    ).value

    expected_route = str((case.get("expected") or {}).get("route") or actual_route)
    expected_intent = intent_from_subtype_hint(subtype_hint) or actual_intent
    expected_intent.title = expected_intent.title or prompt[:80]

    trace: dict[str, Any] = {
        "id": case.get("id"),
        "subtype_hint": subtype_hint,
        "prompt": prompt,
        "expected_effect": case.get("expected_effect"),
        "input": {
            "normalized_input": normalized,
            "layout_instructions": layout_instructions,
        },
        "intent_understanding": understanding,
        "initial_intent": _intent_dict(actual_intent),
        "actual_route": actual_route,
        "expected_route": expected_route,
    }

    try:
        actual_run = _run_route(ctx=ctx, intent=actual_intent, understanding=understanding, route_value=actual_route)
    except Exception as exc:  # keep tracing the remaining cases
        actual_run = {
            "route": actual_route,
            "error": str(exc),
            "traceback": traceback.format_exc(limit=12),
        }
    trace["actual_run"] = actual_run
    trace["actual_evaluation"] = _evaluate_run(case, actual_run)

    try:
        expected_run = _run_route(ctx=ctx, intent=expected_intent, understanding=understanding, route_value=expected_route)
    except Exception as exc:
        expected_run = {
            "route": expected_route,
            "error": str(exc),
            "traceback": traceback.format_exc(limit=12),
        }
    trace["expected_route_probe"] = expected_run
    trace["expected_probe_evaluation"] = _evaluate_run(case, expected_run)
    return _jsonable(trace)


def _status_icon(status: str) -> str:
    if status == "passed":
        return "PASS"
    if status == "warning":
        return "WARN"
    return "FAIL"


def _grammar_label(summary: dict[str, Any]) -> str:
    return str(summary.get("graph_visual_grammar") or summary.get("matrix_visual_grammar") or "")


def _shared_handler_rows(traces: list[dict[str, Any]]) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for trace in traces:
        run = trace.get("actual_run") or {}
        summary = run.get("parsed_spec_summary") or {}
        cls = run.get("classification_summary") or {}
        profile = str(summary.get("render_profile") or cls.get("renderer") or "")
        if not profile:
            profile = str(cls.get("renderer") or trace.get("actual_route") or "unknown")
        groups.setdefault(profile, []).append(trace)

    reasons = {
        "svg.flow": "process-flow grammar owns start/end, branch labels, loop and parallel semantics.",
        "svg.architecture": "architecture grammar owns zones, layers, groups, component cards and orthogonal cross-layer routes.",
        "svg.mechanism": "mechanism grammar owns stage bands, tensor/operation/state roles and feedback lanes.",
        "svg.radial": "radial-concept grammar owns center, satellites, rings and radial links.",
        "svg.network": "network grammar owns clusters, hubs, non-tree layout and relationship labels.",
        "svg.decision": "decision grammar owns top-down tree routing, condition diamonds and yes/no branches.",
        "svg.matrix": "shared matrix renderer because these types share a tabular canvas; it dispatches internally by matrix_visual_grammar, so SWOT and attention do not collapse into a generic table.",
        "svg.timeline": "timeline has a stable axis/event grammar; subtypes can share this while preserving events.",
        "svg.tree": "tree taxonomy has a stable root/children contract and layered layout.",
        "svg.blocks": "infographic blocks share card-grid semantics rather than graph edges.",
        "svg.swimlane": "swimlane is lane-preserving flow grammar with lanes, node_lane and cross-lane routes.",
        "structured.chart": "chart rendering is data-specific and remains outside structured SVG graph grammars.",
        "illustration.image_api": "scene illustration intentionally uses image generation because it is not a structured diagram.",
    }

    rows: list[dict[str, str]] = []
    for profile, items in sorted(groups.items(), key=lambda kv: kv[0]):
        subtypes = [str(t.get("subtype_hint") or t.get("id") or "") for t in items]
        grammars = [
            _grammar_label((t.get("actual_run") or {}).get("parsed_spec_summary") or {})
            for t in items
        ]
        grammars = [g for g in dict.fromkeys(grammars) if g]
        rows.append({
            "profile": profile,
            "subtypes": ", ".join(dict.fromkeys(subtypes)),
            "grammars": ", ".join(grammars) or "-",
            "reason": reasons.get(profile, "shared legacy or route-level handler; inspect subtype grammar before treating it as intentional sharing."),
        })
    return rows


def build_report(traces: list[dict[str, Any]]) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    actual_pass = sum(1 for t in traces if (t.get("actual_evaluation") or {}).get("status") == "passed")
    actual_warning = sum(1 for t in traces if (t.get("actual_evaluation") or {}).get("status") == "warning")
    probe_pass = sum(1 for t in traces if (t.get("expected_probe_evaluation") or {}).get("status") == "passed")
    probe_warning = sum(1 for t in traces if (t.get("expected_probe_evaluation") or {}).get("status") == "warning")
    route_mismatch = [
        t for t in traces
        if t.get("actual_route") != t.get("expected_route")
    ]

    lines = [
        "# 图像生成逐层测试报告",
        "",
        f"生成时间：{generated_at}",
        "",
        "## 测试范围",
        "",
        "本轮测试使用离线确定性模式：`use_llm=False`，每条 case 带 `subtype_hint`。测试目标是覆盖当前规范图类型和一个已支持但未纳入 catalog 主枚举的 `swimlane`，并记录每层输出用于回归测试。",
        "",
        f"- case 数量：{len(traces)}",
        f"- 实际路线完全达标：{actual_pass}/{len(traces)}",
        f"- 实际路线有 warning 但硬字段达标：{actual_warning}/{len(traces)}",
        f"- 期望路线探针完全达标：{probe_pass}/{len(traces)}",
        f"- 期望路线探针有 warning 但硬字段达标：{probe_warning}/{len(traces)}",
        f"- 实际 route 与期望 route 不一致：{len(route_mismatch)}",
        "",
        "输出数据：`autobooker/backend/tests/fixtures/figures/figure_type_pipeline_traces.json`",
        "",
        "## 总览表",
        "",
        "| case | subtype | expected route | actual route | actual | expected probe | 疑似失败层 | 关键降级 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for t in traces:
        ae = t.get("actual_evaluation") or {}
        pe = t.get("expected_probe_evaluation") or {}
        degradations = ae.get("degradations") or []
        if not degradations and pe.get("degradations"):
            degradations = pe.get("degradations") or []
        detail = "<br>".join(f"{d.get('code')}: {d.get('detail')}" for d in degradations[:4]) or "-"
        layers = [
            layer for layer in list(dict.fromkeys(list(ae.get("suspected_layers") or []) + list(pe.get("suspected_layers") or [])))
            if layer != "ok"
        ] or ["ok"]
        layer_text = "<br>".join(layers[:5]) or "-"
        lines.append(
            "| {id} | {subtype} | {expected_route} | {actual_route} | {actual} | {probe} | {layers} | {detail} |".format(
                id=t.get("id"),
                subtype=t.get("subtype_hint"),
                expected_route=t.get("expected_route"),
                actual_route=t.get("actual_route"),
                actual=_status_icon(str(ae.get("status"))),
                probe=_status_icon(str(pe.get("status"))),
                layers=layer_text,
                detail=detail,
            )
        )

    lines.extend([
        "",
        "## 逐层结论",
        "",
    ])
    for t in traces:
        actual = t.get("actual_run") or {}
        probe = t.get("expected_route_probe") or {}
        actual_eval = t.get("actual_evaluation") or {}
        probe_eval = t.get("expected_probe_evaluation") or {}
        actual_spec = actual.get("parsed_spec_summary") or {}
        probe_spec = probe.get("parsed_spec_summary") or {}
        actual_cls = actual.get("classification_summary") or {}
        probe_cls = probe.get("classification_summary") or {}
        lines.extend([
            f"### {t.get('id')} / {t.get('subtype_hint')}",
            "",
            f"- 目标效果：{t.get('expected_effect')}",
            f"- 输入归一化：`{(t.get('input') or {}).get('normalized_input')}`",
            f"- Intent：`{(t.get('initial_intent') or {}).get('diagram_subtype')}` / source=`{(t.get('initial_intent') or {}).get('source')}`",
            f"- 实际 route：`{t.get('actual_route')}`，期望 route：`{t.get('expected_route')}`",
            f"- 实际输出：renderer=`{actual_cls.get('renderer')}`，geometry=`{actual_spec.get('geometry_kind')}`，profile=`{actual_spec.get('render_profile')}`，grammar=`{_grammar_label(actual_spec)}`，status=`{actual_eval.get('status')}`",
            f"- 期望路线探针：renderer=`{probe_cls.get('renderer')}`，geometry=`{probe_spec.get('geometry_kind')}`，profile=`{probe_spec.get('render_profile')}`，grammar=`{_grammar_label(probe_spec)}`，status=`{probe_eval.get('status')}`",
        ])
        section_layers = [
            layer for layer in list(dict.fromkeys(list(actual_eval.get("suspected_layers") or []) + list(probe_eval.get("suspected_layers") or [])))
            if layer != "ok"
        ] or ["ok"]
        lines.append(f"- 疑似失败层：`{', '.join(section_layers)}`")
        notes = []
        for ev in (actual_eval, probe_eval):
            for d in ev.get("degradations") or []:
                note = f"{d.get('code')}: {d.get('detail')}"
                if note not in notes:
                    notes.append(note)
        if notes:
            lines.append("- 降级/未达标：")
            for note in notes[:8]:
                lines.append(f"  - {note}")
        else:
            lines.append("- 降级/未达标：无")
        quality_flags = list(dict.fromkeys(list(actual_eval.get("quality_flags") or []) + list(probe_eval.get("quality_flags") or [])))
        if quality_flags:
            lines.append(f"- 质量 flags：`{', '.join(quality_flags[:12])}`")
        lines.append("")

    lines.extend([
        "## 主要发现",
        "",
    ])
    if route_mismatch:
        lines.append("- 非 structured 类型在离线 `subtype_hint` 模式下存在 route 保真风险：")
        for t in route_mismatch:
            lines.append(f"  - `{t.get('id')}` expected `{t.get('expected_route')}` but actual `{t.get('actual_route')}`")
    else:
        lines.append("- 所有 case 的实际 route 与期望 route 一致。")

    failed_probe = [t for t in traces if (t.get("expected_probe_evaluation") or {}).get("status") == "failed"]
    warning_probe = [t for t in traces if (t.get("expected_probe_evaluation") or {}).get("status") == "warning"]
    if failed_probe:
        lines.append("- 即使强制进入期望 route，以下类型仍存在下游结构/字段/渲染 profile 未达标：")
        for t in failed_probe:
            failures = ", ".join((t.get("expected_probe_evaluation") or {}).get("failures") or [])
            lines.append(f"  - `{t.get('id')}`: {failures}")
    else:
        lines.append("- 强制进入期望 route 后，所有类型下游输出均达标。")
    if warning_probe:
        lines.append("- 以下类型硬字段达标，但仍有质量 warning，后续应作为质量优化项跟进：")
        for t in warning_probe:
            flags = ", ".join((t.get("expected_probe_evaluation") or {}).get("quality_flags") or [])
            lines.append(f"  - `{t.get('id')}`: {flags or 'warning'}")

    lines.extend([
        "",
        "## Shared Handler Decisions",
        "",
        "This table records where subtypes intentionally share a renderer/profile and why. Sharing is acceptable only when the profile still receives a subtype-specific grammar or a stable semantic contract.",
        "",
        "| handler/profile | subtypes | visual grammars | reason |",
        "|---|---|---|---|",
    ])
    for row in _shared_handler_rows(traces):
        lines.append(
            f"| `{row['profile']}` | {row['subtypes']} | {row['grammars']} | {row['reason']} |"
        )

    lines.extend([
        "",
        "## 复跑方式",
        "",
        "```powershell",
        "cd autobooker/backend",
        "$env:PYTHONPATH='.'",
        ".venv\\Scripts\\python.exe scripts\\trace_figure_pipeline_cases.py",
        "```",
        "",
        "该脚本会覆盖更新 trace JSON 和本报告。",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--trace-out", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    traces = [trace_case(case) for case in cases]

    args.trace_out.parent.mkdir(parents=True, exist_ok=True)
    args.trace_out.write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(build_report(traces), encoding="utf-8")

    failed_actual = sum(1 for t in traces if (t.get("actual_evaluation") or {}).get("status") == "failed")
    warning_actual = sum(1 for t in traces if (t.get("actual_evaluation") or {}).get("status") == "warning")
    failed_probe = sum(1 for t in traces if (t.get("expected_probe_evaluation") or {}).get("status") == "failed")
    warning_probe = sum(1 for t in traces if (t.get("expected_probe_evaluation") or {}).get("status") == "warning")
    print(f"traced {len(traces)} cases")
    print(f"actual failures: {failed_actual}")
    print(f"actual warnings: {warning_actual}")
    print(f"expected route probe failures: {failed_probe}")
    print(f"expected route probe warnings: {warning_probe}")
    print(f"trace: {args.trace_out}")
    print(f"report: {args.report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
