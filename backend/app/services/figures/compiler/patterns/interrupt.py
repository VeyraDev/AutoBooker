"""Interrupt Branch Pattern：异常告警/中断。"""

from __future__ import annotations

from typing import Any


def apply_interrupt_branches(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    interrupt_branches: list[dict[str, Any]],
    label_index: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    for i, ib in enumerate(interrupt_branches or []):
        if not isinstance(ib, dict):
            continue
        src = label_index.get(str(ib.get("from") or ""), str(ib.get("from") or ""))
        target_label = str(ib.get("target") or "告警")[:12]
        action = str(ib.get("action") or "alert")
        tgt_id = f"interrupt_{i}"
        nodes.append({
            "id": tgt_id,
            "label": target_label,
            "kind": "end" if action == "abort" else "decision",
        })
        edges.append({
            "from": src,
            "to": tgt_id,
            "label": str(ib.get("on") or "异常"),
            "kind": "interrupt",
        })
    return nodes, edges
