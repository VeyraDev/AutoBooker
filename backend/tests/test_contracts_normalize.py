"""契约：字段归一化。"""

from __future__ import annotations

from app.services.figures.contracts.normalize import (
    normalize_content_brief,
    normalize_graph_decisions,
    normalize_tree_node,
)


def test_normalize_tree_node_string_child():
    node = normalize_tree_node({"label": "根", "children": ["叶A", "叶B"]})
    assert node["children"][0]["label"] == "叶A"
    assert node["children"][1]["label"] == "叶B"


def test_normalize_graph_decisions_fills_yes_no():
    decisions = normalize_graph_decisions([{
        "condition": "是否通过",
        "branches": [{"target": "A"}, {"target": "B"}],
    }])
    labels = [b["label"] for b in decisions[0]["branches"]]
    assert "是" in labels and "否" in labels


def test_normalize_timeline_events():
    content = normalize_content_brief("timeline", {"milestones": [{"year": "2020", "label": "启动"}]})
    assert content["events"][0]["time"] == "2020"
    assert content["events"][0]["label"] == "启动"


def test_normalize_matrix_cells():
    content = normalize_content_brief("comparison_matrix", {
        "subjects": ["A"],
        "dimensions": ["速度"],
        "cells": [{"column": "A", "row": "速度", "text": "快"}],
    })
    assert content["cells"][0]["subject"] == "A"
    assert content["cells"][0]["dimension"] == "速度"
