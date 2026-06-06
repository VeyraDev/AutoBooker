"""箭头 marker 定义。"""

from __future__ import annotations


def arrow_marker_def(marker_id: str = "arrow", *, color: str = "#64748B", size: int = 8) -> str:
    return (
        f'<marker id="{marker_id}" viewBox="0 0 10 10" refX="9" refY="5" '
        f'markerWidth="{size}" markerHeight="{size}" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{color}"/></marker>'
    )
