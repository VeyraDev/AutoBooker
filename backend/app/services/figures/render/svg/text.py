"""SVG 文本换行。"""

from __future__ import annotations

import html

from app.services.figures.design.typography import wrap_label


def multiline_text(x: float, y: float, label: str, *, fill: str, max_width: float, font_size: int = 13, max_lines: int = 3) -> str:
    lines = wrap_label(label, max_width, font_size=font_size)[:max_lines]
    if len(lines) == 1:
        return f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{font_size}" text-anchor="middle" dominant-baseline="middle">{html.escape(lines[0])}</text>'
    parts = []
    line_h = font_size * 1.3
    start_y = y - (len(lines) - 1) * line_h / 2
    for i, line in enumerate(lines):
        parts.append(
            f'<text x="{x:.1f}" y="{start_y + i * line_h:.1f}" fill="{fill}" font-size="{font_size}" text-anchor="middle" dominant-baseline="middle">{html.escape(line)}</text>'
        )
    return "\n".join(parts)
