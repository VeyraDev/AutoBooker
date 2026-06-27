"""AI 生成表格/图解题名（一键排序用）。"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.providers import resolve_book_writing_model
from app.models.book import Book
from app.services.tiptap_convert import _table_cell_text

logger = logging.getLogger(__name__)


def _table_preview_markdown(table: dict[str, Any], max_rows: int = 4) -> str:
    rows = [
        r for r in (table.get("content") or []) if isinstance(r, dict) and r.get("type") == "tableRow"
    ]
    lines: list[str] = []
    for row in rows[:max_rows]:
        cells = [
            c
            for c in (row.get("content") or [])
            if isinstance(c, dict) and c.get("type") in ("tableCell", "tableHeader")
        ]
        texts = [_table_cell_text(c) for c in cells]
        lines.append(" | ".join(texts))
    return "\n".join(lines)


_BAD_TITLE_PATTERNS = (
    r"\[(?:DIAGRAM|FIGURE|FLOWCHART|CHART|SCREENSHOT)\s*:",
    r"请.{0,12}(生成|绘制|画)",
    r"布局脚本",
    r"可见文字白名单",
    r"图类确认",
    r"用户原始输入",
    r"不要输出",
    r"prompt",
)
_GENERIC_TITLE_RE = re.compile(
    r"^(?:本章|章节|内容|整体|综合|核心|总体)?(?:总结|概览|概述|示意|结构|流程|关系|信息|要点)?[图表]$"
)


def _has_bad_prompt_text(text: str) -> bool:
    t = text.strip()
    if "\n" in t or len(t) > 48:
        return True
    return any(re.search(p, t, re.I) for p in _BAD_TITLE_PATTERNS)


def _clean_title(raw: str, *, suffix: str, fallback: str) -> str:
    title = re.sub(r"^```[a-zA-Z0-9_-]*|```$", "", (raw or "").strip())
    title = re.sub(r"^(?:图|表)\s*[\d一二三四五六七八九十百零〇]+(?:[-–—－]\d+)?\s*[:：.．、]?\s*", "", title)
    title = re.sub(r"^[\"'“”‘’「」《》]+|[\"'“”‘’「」《》]+$", "", title).strip()
    title = title.replace("表格", "表").replace("图解", "图")
    title = re.split(r"[\r\n。！？；;]", title, maxsplit=1)[0].strip(" ：:，,")
    if not title or _has_bad_prompt_text(title) or _GENERIC_TITLE_RE.match(title):
        return fallback
    if not title.endswith(suffix):
        title = title.rstrip("表图") + suffix
    if len(title) > 24:
        title = title[:23].rstrip("表图 ：:，,。") + suffix
    return title or fallback


def suggest_table_caption(
    table: dict[str, Any],
    *,
    book: Book,
    context: str = "",
    fallback: str = "本章数据表",
    db: Session | None = None,
) -> str:
    preview = _table_preview_markdown(table)
    if not preview.strip():
        return fallback

    ctx = (context or "").strip()[-800:]
    system = (
        "你是学术图书编辑。根据表格内容与上下文，生成简洁中文表题。"
        "只输出表题文字（8～24字），必须以「表」结尾。"
        "不要编号、不要引号、不要复述表格首行、不要输出解释。"
    )
    user = (
        f"上下文节选（表格前的正文/标题，供理解表格用途）：\n{ctx or '（无）'}\n\n"
        f"表格内容（前若干行）：\n{preview}\n\n"
        "请根据以上信息生成表题："
    )
    try:
        client = LLMClient()
        raw = client.chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=resolve_book_writing_model(book, db=db),
            temperature=0.3,
            max_tokens=64,
        )
        title = _clean_title(raw, suffix="表", fallback=fallback)
        if title:
            return title
    except Exception as e:
        logger.warning("suggest_table_caption failed: %s", e)
    return fallback


def suggest_figure_caption(
    raw_annotation: str,
    *,
    book: Book,
    context: str = "",
    fallback: str = "本章示意图",
    db: Session | None = None,
) -> str:
    ctx = (context or "").strip()[-800:]
    source = (raw_annotation or "").strip()[:1200]
    system = (
        "你是图书编辑。根据图解说明与上下文，生成简洁中文图题。"
        "只输出图题文字（8～24字），必须以「图」结尾。"
        "不要编号、不要引号、不要把完整提示词当题名、不要输出解释。"
    )
    user = (
        f"上下文节选（图前正文/标题，供理解图解用途）：\n{ctx or '（无）'}\n\n"
        f"图解说明：\n{source or '（无）'}\n\n"
        "请生成简短图题："
    )
    try:
        client = LLMClient()
        raw = client.chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=resolve_book_writing_model(book, db=db),
            temperature=0.2,
            max_tokens=64,
        )
        title = _clean_title(raw, suffix="图", fallback=fallback)
        if title:
            return title
    except Exception as e:
        logger.warning("suggest_figure_caption failed: %s", e)
    return fallback
