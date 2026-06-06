"""Node size estimation used by layout strategies."""

from __future__ import annotations

from app.services.figures.design.typography import estimate_text_width


def estimate_node_size(label: str, *, min_width: float = 116.0, max_width: float = 220.0) -> tuple[float, float]:
    text = str(label or "")
    raw_width = estimate_text_width(text, font_size=13) + 24
    width = max(min_width, min(max_width, raw_width))
    line_capacity = max(1.0, (width - 24) / 13)
    visual_units = sum(1.0 if "\u4e00" <= ch <= "\u9fff" else 0.55 for ch in text)
    lines = max(1, min(3, int((visual_units + line_capacity - 1) // line_capacity)))
    height = max(46.0, 24.0 + lines * 18.0)
    return width, height
