"""Pipeline 辅助函数。"""

from __future__ import annotations

from typing import Any


def spec_to_flowchart_description(render_spec: dict[str, Any], *, title: str = "") -> str:
    nodes = render_spec.get("nodes") or []
    edges = render_spec.get("edges") or []
    layout = str(render_spec.get("layout") or "TB").upper()
    layout_hint = "自上而下" if layout == "TB" else "自左向右"
    lines: list[str] = []
    if title:
        lines.append(f"标题：{title}")
    lines.append(f"布局：{layout_hint}")
    for n in nodes[:20]:
        if not isinstance(n, dict):
            continue
        label = str(n.get("label") or "").strip()
        shape = str(n.get("shape") or "box").strip()
        nid = str(n.get("id") or label).strip()
        if label:
            lines.append(f"- [{shape}] {nid}: {label}")
    for e in edges[:30]:
        if not isinstance(e, dict):
            continue
        src = str(e.get("from") or "").strip()
        dst = str(e.get("to") or "").strip()
        lbl = str(e.get("label") or "").strip()
        if src and dst:
            lines.append(f"- {src} → {dst}" + (f"（{lbl}）" if lbl else ""))
    return "\n".join(lines) if lines else title
