"""全局字段别名注册表 — Brief/Compiler/Projector 唯一归一词典。"""

from __future__ import annotations

from typing import Any

# canonical_field -> aliases (first match wins on read)
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "label": ("name", "title", "text", "event"),
    "condition": ("question", "prompt", "if"),
    "time": ("year", "date", "when", "period"),
    "subject": ("column", "col"),
    "dimension": ("row", "axis", "criterion"),
    "value": ("text", "content", "score"),
}

TREE_NODE_FIELDS = ("label", "children", "id")


def pick_field(data: dict[str, Any], canonical: str, default: Any = "") -> Any:
    if not isinstance(data, dict):
        return default
    if data.get(canonical) not in (None, ""):
        return data.get(canonical)
    for alias in FIELD_ALIASES.get(canonical, ()):
        val = data.get(alias)
        if val not in (None, ""):
            return val
    return default


def pick_str(data: dict[str, Any], canonical: str, default: str = "") -> str:
    val = pick_field(data, canonical, default)
    return str(val).strip() if val is not None else default
