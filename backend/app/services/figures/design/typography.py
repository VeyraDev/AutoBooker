"""文字测量（简化版）。"""

from __future__ import annotations


def estimate_text_width(text: str, *, font_size: int = 13) -> float:
    w = 0.0
    for ch in str(text or ""):
        if "\u4e00" <= ch <= "\u9fff":
            w += font_size
        else:
            w += font_size * 0.55
    return w + 16


def wrap_label(text: str, max_width: float, *, font_size: int = 13) -> list[str]:
    if estimate_text_width(text, font_size=font_size) <= max_width:
        return [text]
    lines: list[str] = []
    buf = ""
    for ch in text:
        trial = buf + ch
        if estimate_text_width(trial, font_size=font_size) > max_width and buf:
            lines.append(buf)
            buf = ch
        else:
            buf = trial
    if buf:
        lines.append(buf)
    return lines[:3]


def measure_node_size(label: str, *, font_size: int = 13, min_w: float = 96, max_w: float = 168) -> tuple[float, float]:
    lines = wrap_label(label, max_w - 16, font_size=font_size)
    line_h = font_size * 1.35
    height = max(40.0, len(lines) * line_h + 16)
    width = min(max_w, max(min_w, max(estimate_text_width(ln, font_size=font_size) for ln in lines) + 20))
    return width, height
