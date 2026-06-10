"""Dependency Pattern：多前置 AND 门禁。"""

from __future__ import annotations

from typing import Any


def apply_dependencies(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
    label_index: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    for i, dep in enumerate(dependencies or []):
        if not isinstance(dep, dict):
            continue
        requires = [str(x) for x in (dep.get("requires") or [])]
        enables = str(dep.get("enables") or "")
        if len(requires) < 2 or not enables:
            continue
        gate_id = f"dep_gate_{i}"
        nodes.append({"id": gate_id, "label": "依赖汇合", "kind": "parallel_join"})
        tgt = label_index.get(enables, enables)
        for req in requires:
            src = label_index.get(req, req)
            edges.append({"from": src, "to": gate_id})
        edges.append({"from": gate_id, "to": tgt})
    return nodes, edges
