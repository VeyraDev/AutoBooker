"""风格语料向量检索（占位）。接入 style_corpus 表后可在此实现向量检索。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_style_examples(style_type: str | None, query: str, *, top_k: int = 3, db=None) -> str:
    del query, top_k, db
    if not style_type:
        return "（暂无同风格参考示例；请严格遵循体裁提示与 user_material。）"
    return (
        f"（风格向量库尚未接入；当前体裁为 {style_type}，"
        "请以下文「体裁与章节风格指令」为准进行写作。）"
    )


def get_intro_examples(style_type: str | None, *, db=None) -> str:
    del db
    if not style_type:
        return ""
    return f"（开篇示例库尚未接入；体裁：{style_type}）"
