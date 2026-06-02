"""输入归一化。"""

from __future__ import annotations

import re


def normalize_figure_input(
    text: str,
    *,
    user_hint: str = "",
    figure_annotation: str = "",
) -> str:
    parts: list[str] = []
    hint = (user_hint or "").strip()
    ann = (figure_annotation or "").strip()
    raw = (text or "").strip()

    if ann and ann not in raw:
        parts.append(ann)
    if raw:
        parts.append(raw)
    if hint and hint not in "\n".join(parts):
        parts.append(hint)

    merged = "\n".join(p for p in parts if p).strip()
    merged = re.sub(r"\[(?:FIGURE|DIAGRAM|FLOWCHART|CHART|SCREENSHOT):\s*", "", merged, flags=re.I)
    merged = re.sub(r"\]\s*$", "", merged.strip())
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return merged.strip()
