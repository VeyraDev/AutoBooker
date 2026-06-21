"""Grammar 管线覆盖：各 structured 类型共用桥接，非 taxonomy 单点补丁。"""

from __future__ import annotations

import pytest

from app.services.figures.graph.metrics import compute_graph_metrics
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.pipeline.grammar_bridge import (
    build_graph_from_grammar_spec,
    grammar_spec_usable,
    grammar_uses_graph_layout,
)
from app.services.figures.schemas.diagram import DiagramIntent

# 各类型最小 grammar spec 样例（与 parser _to_graph 字段对齐）
GRAMMAR_FIXTURES: list[tuple[str, dict, bool]] = [
    (
        "process_flow",
        {
            "title": "流程",
            "stages": [{"id": "s0", "label": "A"}, {"id": "s1", "label": "B"}],
            "nodes": [
                {"id": "s0", "label": "A"},
                {"id": "s1", "label": "B"},
            ],
            "edges": [{"from": "s0", "to": "s1"}],
        },
        False,
    ),
    (
        "taxonomy_map",
        {
            "title": "分类",
            "root": "根",
            "children": [{"label": "A", "children": [{"label": "A1"}]}],
            "nodes": [
                {"id": "root", "label": "根"},
                {"id": "c0", "label": "A"},
                {"id": "c0_0", "label": "A1", "parent": "c0"},
            ],
            "edges": [
                {"from": "root", "to": "c0"},
                {"from": "c0", "to": "c0_0"},
            ],
        },
        False,
    ),
    (
        "system_architecture",
        {
            "title": "架构",
            "layers": [{"label": "服务层", "modules": ["API", "DB"]}],
            "nodes": [
                {"id": "l0_m0", "label": "API"},
                {"id": "l0_m1", "label": "DB"},
            ],
            "edges": [{"from": "l0_m0", "to": "l0_m1"}],
        },
        False,
    ),
    (
        "timeline_roadmap",
        {
            "title": "路线",
            "events": [{"time": "T1", "label": "启动"}, {"time": "T2", "label": "发布"}],
            "nodes": [
                {"id": "e0", "label": "T1 启动"},
                {"id": "e1", "label": "T2 发布"},
            ],
            "edges": [{"from": "e0", "to": "e1"}],
        },
        False,
    ),
    (
        "infographic",
        {
            "title": "信息图",
            "blocks": [{"label": "块1", "items": []}],
            "nodes": [
                {"id": "summary", "label": "信息图"},
                {"id": "b0", "label": "块1"},
            ],
            "edges": [{"from": "summary", "to": "b0"}],
        },
        False,
    ),
    (
        "comparison_matrix",
        {
            "title": "对比",
            "columns": ["A", "B"],
            "dimensions": ["成本", "速度"],
            "nodes": [
                {"id": "matrix", "label": "对比"},
                {"id": "d0", "label": "成本"},
            ],
            "edges": [{"from": "matrix", "to": "d0"}],
        },
        False,
    ),
    (
        "swot",
        {
            "title": "SWOT",
            "strengths": ["优势"],
            "weaknesses": ["劣势"],
            "opportunities": ["机会"],
            "threats": ["威胁"],
        },
        True,
    ),
    (
        "attention_matrix",
        {"title": "注意力", "size": 12, "window": 4},
        True,
    ),
    (
        "concept_diagram",
        {
            "title": "概念",
            "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "edges": [{"from": "a", "to": "b"}],
        },
        False,
    ),
]


@pytest.mark.parametrize("subtype,spec,usable", GRAMMAR_FIXTURES)
def test_grammar_spec_usable_all_structured_types(subtype: str, spec: dict, usable: bool):
    intent = DiagramIntent("workflow", subtype, 0.9, "test", spec.get("title", ""), diagram_type="flowchart")
    assert grammar_spec_usable(spec, intent) is usable


@pytest.mark.parametrize("subtype,spec,_", [f for f in GRAMMAR_FIXTURES if grammar_uses_graph_layout(f[0])])
def test_build_graph_from_grammar_spec_graph_types(subtype: str, spec: dict, _: bool):
    intent = DiagramIntent("workflow", subtype, 0.9, "test", spec.get("title", ""))
    graph = build_graph_from_grammar_spec(spec, intent)
    metrics = compute_graph_metrics(graph)
    assert metrics["node_count"] >= 2
    hints = (graph.layout_constraints or {}).get("hints") or []
    if subtype == "taxonomy_map":
        assert "tree_tb" in hints
    if subtype == "system_architecture":
        assert "layered_architecture" in hints or "layered" in str(hints)


def test_swot_and_attention_skip_graph_layout():
    assert not grammar_uses_graph_layout("swot")
    assert not grammar_uses_graph_layout("attention_matrix")


def test_taxonomy_depth_preserved_in_graph():
    spec = GRAMMAR_FIXTURES[1][1]
    intent = DiagramIntent("knowledge", "taxonomy_map", 0.9, "test", "分类")
    graph = build_graph_from_grammar_spec(spec, intent)
    metrics = compute_graph_metrics(graph)
    assert metrics["max_depth"] >= 2
    assert canonical_subtype(intent.diagram_subtype) == "taxonomy_map"
