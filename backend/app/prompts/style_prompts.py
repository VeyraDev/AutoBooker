"""按 style_type 加载 prompts/styles 下的体裁文件（大纲段 + 章节段）。"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.constants.style_types import STYLE_PROMPT_BASENAME, StyleType

_STYLES_DIR = Path(__file__).resolve().parent / "styles"
_CHAPTER_SPLIT = re.compile(r"【章节生成 prompt】", re.M)


def _read_file(stem: str) -> str:
    path = _STYLES_DIR / f"{stem}.txt"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=32)
def _cached_parts(style_value: str) -> tuple[str, str]:
    try:
        st = StyleType(style_value)
    except ValueError:
        return "", ""
    stem = STYLE_PROMPT_BASENAME.get(st)
    if not stem:
        return "", ""
    raw = _read_file(stem)
    if not raw.strip():
        return "", ""
    parts = _CHAPTER_SPLIT.split(raw, maxsplit=1)
    outline = parts[0].replace("【大纲生成 prompt】", "").strip()
    chapter = parts[1].strip() if len(parts) > 1 else ""
    return outline, chapter


def get_outline_style_prompt(style_type: str | StyleType | None) -> str:
    key = style_type.value if isinstance(style_type, StyleType) else (style_type or "")
    o, _ = _cached_parts(key)
    return o


def get_chapter_style_prompt(style_type: str | StyleType | None) -> str:
    key = style_type.value if isinstance(style_type, StyleType) else (style_type or "")
    _, c = _cached_parts(key)
    return c


def clear_style_prompt_cache() -> None:
    _cached_parts.cache_clear()
