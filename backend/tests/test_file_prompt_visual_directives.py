"""Regression coverage for docs/figure_type_test_prompts.md.

These cases are intentionally separate from the catalog fixtures: the docs file
contains more explicit visual instructions such as color encoding, two-column
shared resources, and bidirectional arrows.  The DIAGRAM prompt is the only
classification input; the "期望" line is retained as evaluation metadata.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.figures.pipeline.orchestrator import classify_figure_description

DOC_PATH = Path(__file__).resolve().parents[3] / "docs" / "figure_type_test_prompts.md"

SKIPPED_TYPES = {"data_visualization", "scene_illustration", "screenshot"}
EDGE_SUBTYPES = {
    "E-1": "process_flow",
    "E-2": "process_flow",
    "E-3": "process_flow",
    "E-4": "process_flow",
    "E-5": "system_architecture",
}

EXPECTED_DIRECTIVES = {
    "1-B": {"layout.parallel", "edge.feedback", "node.decision_shape"},
    "2-C": {"layout.columns", "layout.shared_resource", "edge.label"},
    "4-B": {"node.decision_shape", "edge.branch_label"},
    "5-A": {"layout.timeline"},
    "6-A": {"comparison.axis", "encoding.color_scale"},
    "6-B": {"comparison.axis", "comparison.quantitative_form"},
    "7-A": {"semantic.qkv", "notation.matrix"},
    "7-B": {"layout.encoder_decoder", "layout.stack"},
    "7-C": {"edge.bidirectional", "encoding.color_scale"},
    "8-A": {"layout.radial"},
    "8-B": {"edge.relationship_label"},
    "11-A": {"layout.card_grid", "encoding.iconic", "encoding.palette"},
    "11-B": {"layout.card_grid", "layout.columns", "encoding.palette"},
    "E-2": {"readability.mixed_text"},
    "E-3": {"routing.numeric_attribute"},
    "E-4": {"complexity.summarize", "encoding.color_scale"},
}


def _doc_cases() -> dict[str, dict[str, str]]:
    text = DOC_PATH.read_text(encoding="utf-8")
    cases: dict[str, dict[str, str]] = {}
    current_type = ""
    current_num = ""
    for line in text.splitlines():
        m = re.match(r"### .*?类型\s+(\d+)：([a-z_]+)", line)
        if m:
            current_num, current_type = m.group(1), m.group(2)
            continue
        m = re.match(r"\*\*测试\s+([^：]+)：", line)
        if m:
            current_num = m.group(1)
            continue
        m = re.match(r"\[(DIAGRAM|SCREENSHOT):\s*(.*?)\]", line)
        if m:
            case_id = current_num.strip()
            cases[case_id] = {
                "id": case_id,
                "kind": m.group(1),
                "subtype": EDGE_SUBTYPES.get(case_id, current_type),
                "prompt": m.group(2).strip(),
            }
            continue
        if line.startswith("期望：") and current_num.strip() in cases:
            cases[current_num.strip()]["expected"] = line.removeprefix("期望：").strip()
    return cases


def _classify(case_id: str) -> dict:
    case = _doc_cases()[case_id]
    return classify_figure_description(
        case["prompt"],
        use_llm=False,
        model="",
        subtype_hint=case["subtype"],
    )


def _directive_ids(record: dict) -> set[str]:
    spec = record.get("parsed_spec") or {}
    return set(str(x) for x in (spec.get("directive_ids") or []) if str(x))


def test_docs_file_structured_cases_are_separate_and_skip_image_or_chart_types():
    cases = _doc_cases()
    runnable = [c for c in cases.values() if c["kind"] == "DIAGRAM" and c["subtype"] not in SKIPPED_TYPES]
    skipped = [c for c in cases.values() if c["subtype"] in SKIPPED_TYPES or c["kind"] == "SCREENSHOT"]

    assert len(runnable) == 26
    assert {c["subtype"] for c in skipped} >= {"data_visualization", "scene_illustration", "screenshot"}
    assert any(c["subtype"] == "infographic" for c in runnable)
    assert all("期望" not in c["prompt"] for c in runnable)


def test_file_prompt_cases_default_to_image_api_renderer():
    for case_id, _expected in EXPECTED_DIRECTIVES.items():
        record = _classify(case_id)
        spec = record.get("parsed_spec") or {}

        assert record["renderer"] == "illustration.image_api", case_id
        assert spec["render_mode"] == "image_api", case_id


def test_file_prompt_comparison_prefers_matrix_for_color_encoded_dimensions():
    record = _classify("6-A")
    spec = record["parsed_spec"]

    assert record["diagram_subtype"] == "comparison_matrix"
    assert record["renderer"] == "illustration.image_api"
    assert spec["render_mode"] == "image_api"


def test_file_prompt_architecture_two_column_shared_node_routes_to_image_api():
    record = _classify("2-C")
    spec = record["parsed_spec"]

    assert record["diagram_subtype"] == "system_architecture"
    assert record["renderer"] == "illustration.image_api"
    assert spec["render_mode"] == "image_api"


def test_file_prompt_mechanism_bidirectional_arrows_routes_to_image_api():
    record = _classify("7-C")
    spec = record["parsed_spec"]

    assert record["diagram_subtype"] == "mechanism_diagram"
    assert record["renderer"] == "illustration.image_api"
    assert spec["render_mode"] == "image_api"


def test_file_prompt_numeric_flow_guard_does_not_route_to_chart():
    record = _classify("E-3")

    assert record["diagram_subtype"] == "process_flow"
    assert record["renderer"] != "structured.chart"
    assert record["renderer"] == "illustration.image_api"


def test_file_prompt_infographic_routes_to_image_api():
    record = _classify("11-A")
    spec = record["parsed_spec"]

    assert record["diagram_subtype"] == "infographic"
    assert record["renderer"] == "illustration.image_api"
    assert spec["render_mode"] == "image_api"
