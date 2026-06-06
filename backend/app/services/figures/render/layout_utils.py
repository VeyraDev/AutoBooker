"""Layout helpers for book-quality figure rendering."""

from __future__ import annotations

import math
import re
from typing import Iterable

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def visual_width(text: str) -> float:
    """Approximate visual width. CJK chars are wider than latin chars."""
    total = 0.0
    for ch in str(text or ""):
        if ch == "\n":
            continue
        if _CJK_RE.match(ch):
            total += 1.0
        elif ch.isspace():
            total += 0.35
        else:
            total += 0.55
    return total


def _tokenize(text: str) -> list[str]:
    """Keep CJK characters wrappable while preserving latin words."""
    tokens: list[str] = []
    buf = ""
    for ch in str(text or ""):
        if _CJK_RE.match(ch):
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        elif ch.isspace():
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(" ")
        elif ch in "/,，、;；:：|·-—()（）[]【】":
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        else:
            buf += ch
    if buf:
        tokens.append(buf)
    return tokens


def wrap_text(text: str, *, max_units: float = 12, max_lines: int = 3) -> str:
    """Wrap mixed Chinese/English text for matplotlib nodes."""
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    if not raw:
        return ""
    lines: list[str] = []
    cur = ""
    for token in _tokenize(raw):
        candidate = (cur + token).strip() if token != " " else cur + token
        if cur and visual_width(candidate) > max_units:
            lines.append(cur.strip())
            cur = token.strip()
        else:
            cur = candidate
    if cur.strip():
        lines.append(cur.strip())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        # Make truncation explicit at a line boundary; never slice Latin words.
        lines[-1] = lines[-1].rstrip("。；;，,、 ") + "…"
    return "\n".join(lines)


def max_line_width(wrapped_text: str) -> float:
    return max((visual_width(line) for line in str(wrapped_text or "").splitlines()), default=0.0)


def measure_text(label: str, *, max_units: float = 12, max_lines: int = 3) -> dict[str, float | str | int]:
    """测量文本换行后的尺寸信息。"""
    wrapped = wrap_text(label, max_units=max_units, max_lines=max_lines)
    lines = max(1, len(wrapped.splitlines()))
    width_units = max_line_width(wrapped)
    return {
        "wrapped": wrapped,
        "width_units": width_units,
        "lines": lines,
        "height_units": 0.31 * lines + 0.42,
    }


def estimate_node_size(
    label: str,
    *,
    shape: str = "box",
    max_units: float = 12,
    max_lines: int = 3,
) -> tuple[str, float, float]:
    wrapped = wrap_text(label, max_units=max_units, max_lines=max_lines)
    lines = max(1, len(wrapped.splitlines()))
    width_units = max_line_width(wrapped)
    if shape == "tag":
        w = max(1.3, min(2.65, width_units * 0.20 + 0.5))
        h = max(0.42, 0.28 * lines + 0.2)
    elif shape == "diamond":
        w = max(2.75, min(4.5, width_units * 0.22 + 1.0))
        h = max(1.05, 0.32 * lines + 0.62)
    else:
        w = max(2.35, min(4.15, width_units * 0.22 + 0.72))
        h = max(0.82, 0.31 * lines + 0.42)
    return wrapped, w, h


def clamp_font_size(label: str, *, base: float = 9.0, min_size: float = 6.6) -> float:
    vw = visual_width(label)
    if vw <= 16:
        return base
    return max(min_size, base - math.log(vw / 16 + 1, 2) * 0.9)
