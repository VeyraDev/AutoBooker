"""AI 生成表格表题（一键排序用）。"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.llm.client import LLMClient
from app.llm.providers import resolve_book_writing_model
from app.models.book import Book
from app.services.tiptap_convert import _inline_to_markdown, _table_cell_text

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


def suggest_table_caption(
    table: dict[str, Any],
    *,
    book: Book,
    context: str = "",
    fallback: str = "附表",
) -> str:
    preview = _table_preview_markdown(table)
    if not preview.strip():
        return fallback

    ctx = (context or "").strip()[-800:]
    system = (
        "你是学术图书编辑。根据表格内容与上下文，生成简洁中文表题。"
        "只输出表题文字（8～24字），不要编号、不要引号、不要「表」字前缀。"
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
            model=resolve_book_writing_model(book),
            temperature=0.3,
            max_tokens=64,
        )
        title = re.sub(r"^表\s*[\d\-—：:]+", "", (raw or "").strip())
        title = title.strip("「」\"'：: ")
        if 4 <= len(title) <= 48:
            return title
    except Exception as e:
        logger.warning("suggest_table_caption failed: %s", e)
    return fallback
