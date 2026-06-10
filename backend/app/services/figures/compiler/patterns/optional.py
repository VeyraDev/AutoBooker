"""Optional Branch Pattern：可跳过支路。"""

from __future__ import annotations

from typing import Any


def apply_optional_branches(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    optional_branches: list[dict[str, Any]],
    label_index: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    for i, ob in enumerate(optional_branches or []):
        if not isinstance(ob, dict):
            continue
        after = label_index.get(str(ob.get("after") or ""), str(ob.get("after") or ""))
        label = str(ob.get("label") or "可选步骤")[:16]
        opt_id = f"opt_{i}"
        nodes.append({"id": opt_id, "label": label, "kind": "task", "optional": True})
        edges.append({"from": after, "to": opt_id, "label": "可选", "kind": "optional"})
    return nodes, edges
