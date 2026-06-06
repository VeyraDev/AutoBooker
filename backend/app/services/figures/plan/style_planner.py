"""样式建议器（render_planner 布局职能已迁至 layout/）。"""

from __future__ import annotations

from app.services.figures.schemas.dsl import DiagramDSL

_THEME_HINTS = {
    "企业": "modern_saas",
    "saas": "modern_saas",
    "学术": "academic_clean",
    "书稿": "academic_clean",
}


def apply_style_hints(dsl: DiagramDSL, *hint_lists: list[str]) -> DiagramDSL:
    hints: list[str] = []
    for hl in hint_lists:
        hints.extend(hl or [])
    theme = dsl.style.get("theme") or "modern_saas"
    for h in hints:
        low = h.lower()
        for key, val in _THEME_HINTS.items():
            if key in low:
                theme = val
    dsl.style = dict(dsl.style or {})
    dsl.style["theme"] = theme
    for node in dsl.nodes:
        if node.type == "decision":
            node.shape = node.shape or "diamond"
        elif node.type == "gateway":
            node.color = node.color or "#FEF3C7"
        elif node.type == "queue":
            node.color = node.color or "#ECFEFF"
    return dsl
