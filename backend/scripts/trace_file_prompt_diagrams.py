"""Run docs/figure_type_test_prompts.md DIAGRAM cases without using expectations as input."""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.figures.pipeline.orchestrator import classify_figure_description
from app.services.figures.render.svg.comparison import render_comparison_svg
from app.services.figures.render.svg.graph_grammar import render_graph_grammar_svg
from app.services.figures.render.svg.renderer import render_svg_diagram
from app.services.figures.render.svg.timeline import render_timeline_svg
from app.services.figures.render.structured.grammar import generate_infographic_diagram

DEFAULT_DOC = WORKSPACE_ROOT / "docs" / "figure_type_test_prompts.md"
DEFAULT_TRACE = BACKEND_ROOT / "tests" / "fixtures" / "figures" / "file_prompt_diagram_traces.json"
DEFAULT_REPORT = WORKSPACE_ROOT / "docs" / "图像生成文件用例运行报告.md"
DEFAULT_OUT_DIR = BACKEND_ROOT / "tests" / "fixtures" / "figures" / "file_prompt_outputs"

SKIPPED_SUBTYPES = {"data_visualization", "scene_illustration"}
EDGE_SUBTYPES = {
    "E-1": "process_flow",
    "E-2": "process_flow",
    "E-3": "process_flow",
    "E-4": "process_flow",
    "E-5": "system_architecture",
}


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


def parse_cases(doc_path: Path) -> list[dict[str, str]]:
    text = doc_path.read_text(encoding="utf-8")
    cases: list[dict[str, str]] = []
    current_type = ""
    current_id = ""
    current_case: dict[str, str] | None = None
    for line in text.splitlines():
        m = re.match(r"### .*?类型\s+(\d+)：([a-z_]+)", line)
        if m:
            current_type = m.group(2)
            current_id = m.group(1)
            current_case = None
            continue
        m = re.match(r"\*\*测试\s+([^：]+)：", line)
        if m:
            current_id = m.group(1).strip()
            current_case = None
            continue
        m = re.match(r"\[(DIAGRAM|SCREENSHOT):\s*(.*?)\]", line)
        if m:
            subtype = EDGE_SUBTYPES.get(current_id, current_type)
            current_case = {
                "id": current_id,
                "kind": m.group(1),
                "subtype": subtype,
                "prompt": m.group(2).strip(),
                "expected": "",
            }
            cases.append(current_case)
            continue
        if current_case is not None and line.startswith("期望："):
            current_case["expected"] = line.removeprefix("期望：").strip()
    return cases


def runnable_cases(cases: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        c for c in cases
        if c.get("kind") == "DIAGRAM" and c.get("subtype") not in SKIPPED_SUBTYPES
    ]


def _spec_summary(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagram_subtype": spec.get("diagram_subtype"),
        "geometry_kind": spec.get("geometry_kind"),
        "render_profile": spec.get("render_profile"),
        "graph_visual_grammar": spec.get("graph_visual_grammar"),
        "matrix_visual_grammar": spec.get("matrix_visual_grammar"),
        "directive_ids": list(spec.get("directive_ids") or []),
        "mandatory_semantics": list(spec.get("mandatory_semantics") or []),
        "node_count": len(spec.get("nodes") or []),
        "edge_count": len(spec.get("edges") or []),
        "event_count": len(spec.get("events") or []),
        "block_count": len(spec.get("blocks") or []),
        "cell_count": len(spec.get("cells") or []),
        "quality_flags": list(spec.get("quality_flags") or []),
    }


def _render_case(case: dict[str, str], record: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    spec = record.get("parsed_spec") if isinstance(record.get("parsed_spec"), dict) else {}
    profile = str(spec.get("render_profile") or "")
    out_path = out_dir / f"{case['id'].replace('-', '_')}.png"
    title = str(spec.get("title") or record.get("prompt_spec", {}).get("title") or case["id"])
    try:
        if profile in {"svg.flow", "svg.architecture", "svg.mechanism", "svg.radial", "svg.network", "svg.decision"}:
            _, path = render_graph_grammar_svg(spec, out_path, title=title, design_spec=spec.get("design_spec"))
        elif profile == "svg.matrix":
            _, path = render_comparison_svg(spec, out_path, title=title, design_spec=spec.get("design_spec"))
        elif profile == "svg.timeline":
            _, path = render_timeline_svg(spec, out_path, title=title, design_spec=spec.get("design_spec"))
        elif profile == "svg.blocks":
            _, path = generate_infographic_diagram(spec, out_path, title=title)
        elif profile in {"svg.tree", "svg.graph", "svg.swimlane"} and (record.get("layout_result") or spec.get("layout_result")):
            _, path = render_svg_diagram(
                spec,
                out_path,
                title=title,
                layout_result=record.get("layout_result") or spec.get("layout_result"),
                design_spec=spec.get("design_spec"),
            )
        else:
            return {"status": "skipped", "reason": f"unsupported profile {profile}"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "traceback": traceback.format_exc(limit=8)}
    return {"status": "rendered", "path": str(path), "profile": profile}


def _evaluate(case: dict[str, str], record: dict[str, Any], render: dict[str, Any]) -> dict[str, Any]:
    spec = record.get("parsed_spec") if isinstance(record.get("parsed_spec"), dict) else {}
    expected = case.get("expected") or ""
    ids = set(str(x) for x in (spec.get("directive_ids") or []))
    failures: list[str] = []
    warnings: list[str] = []
    if render.get("status") != "rendered":
        failures.append("render_not_produced")
    if "颜色" in expected or "色块" in expected:
        if "encoding.color_scale" not in ids and "encoding.palette" not in ids:
            warnings.append("expected_color_semantics_not_explicit")
    if "两列" in expected or "左右" in expected:
        if "layout.columns" not in ids and "layout.encoder_decoder" not in ids:
            warnings.append("expected_column_layout_not_explicit")
    if "箭头" in expected and ("标签" in expected or "标注" in expected):
        if not ({"edge.label", "edge.branch_label", "edge.relationship_label"} & ids):
            warnings.append("expected_labeled_edges_not_explicit")
    if "矩阵" in expected and "notation.matrix" not in ids and spec.get("matrix_visual_grammar") != "attention_heatmap":
        warnings.append("expected_matrix_notation_not_explicit")
    if "图标" in expected and "encoding.iconic" not in ids:
        warnings.append("expected_iconic_encoding_not_explicit")
    return {
        "status": "failed" if failures else ("warning" if warnings else "passed"),
        "failures": failures,
        "warnings": warnings,
    }


def trace_case(case: dict[str, str], out_dir: Path) -> dict[str, Any]:
    record = classify_figure_description(
        case["prompt"],
        use_llm=False,
        model="",
        subtype_hint=case["subtype"],
    )
    spec = record.get("parsed_spec") if isinstance(record.get("parsed_spec"), dict) else {}
    render = _render_case(case, record, out_dir)
    evaluation = _evaluate(case, record, render)
    return {
        "id": case["id"],
        "subtype_hint": case["subtype"],
        "prompt": case["prompt"],
        "expected": case.get("expected") or "",
        "classification_summary": {
            "diagram_subtype": record.get("diagram_subtype"),
            "renderer": record.get("renderer"),
            "image_type": record.get("image_type"),
            "layout_strategy": record.get("layout_strategy"),
            "quality_flags": list(record.get("quality_flags") or []),
            "render_warnings": list(record.get("render_warnings") or []),
        },
        "parsed_spec_summary": _spec_summary(spec),
        "render": render,
        "evaluation": evaluation,
    }


def build_report(traces: list[dict[str, Any]], skipped: list[dict[str, str]]) -> str:
    passed = sum(1 for t in traces if (t.get("evaluation") or {}).get("status") == "passed")
    warnings = sum(1 for t in traces if (t.get("evaluation") or {}).get("status") == "warning")
    failed = sum(1 for t in traces if (t.get("evaluation") or {}).get("status") == "failed")
    lines = [
        "# 图像生成文件用例运行报告",
        "",
        "输入来源：`docs/figure_type_test_prompts.md`。",
        "",
        "规则：只将 `[DIAGRAM: ...]` 内容作为系统输入；`期望` 只用于结果评价；跳过 type 9 数据图、type 10 插图和 screenshot 占位。",
        "",
        f"- 运行 DIAGRAM：{len(traces)}",
        f"- 跳过：{len(skipped)}",
        f"- passed：{passed}",
        f"- warning：{warnings}",
        f"- failed：{failed}",
        "",
        "| case | subtype | renderer/profile | directives | render | evaluation | notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for trace in traces:
        summary = trace.get("parsed_spec_summary") or {}
        cls = trace.get("classification_summary") or {}
        ev = trace.get("evaluation") or {}
        notes = ", ".join(list(ev.get("failures") or []) + list(ev.get("warnings") or [])) or "-"
        directives = ", ".join(summary.get("directive_ids") or []) or "-"
        render = trace.get("render") or {}
        render_state = render.get("status")
        if render.get("path"):
            render_state += f"<br>`{render.get('path')}`"
        lines.append(
            f"| {trace.get('id')} | {trace.get('subtype_hint')} | {cls.get('renderer')} / {summary.get('render_profile')} | {directives} | {render_state} | {ev.get('status')} | {notes} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--trace-out", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    all_cases = parse_cases(args.doc)
    run_cases = runnable_cases(all_cases)
    skipped = [c for c in all_cases if c not in run_cases]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    traces = [trace_case(case, args.out_dir) for case in run_cases]

    args.trace_out.parent.mkdir(parents=True, exist_ok=True)
    args.trace_out.write_text(json.dumps(_jsonable(traces), ensure_ascii=False, indent=2), encoding="utf-8")
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(build_report(traces, skipped), encoding="utf-8")

    failed = sum(1 for t in traces if (t.get("evaluation") or {}).get("status") == "failed")
    warnings = sum(1 for t in traces if (t.get("evaluation") or {}).get("status") == "warning")
    print(f"runnable cases: {len(traces)}")
    print(f"skipped cases: {len(skipped)}")
    print(f"failures: {failed}")
    print(f"warnings: {warnings}")
    print(f"trace: {args.trace_out}")
    print(f"report: {args.report_out}")
    print(f"outputs: {args.out_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

