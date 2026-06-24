"""全书叙事宪法 / 体例宪法（NarrativeAgent），见 docs/prompt.md。"""

from __future__ import annotations

import logging
from typing import Literal

from app.constants.style_types import StyleType, coerce_style
from app.llm.client import LLMClient
from app.models.book import Book
from app.prompts.narrative_prompts import NARRATIVE_SYSTEM_A, NARRATIVE_SYSTEM_B, NARRATIVE_SYSTEM_C

logger = logging.getLogger(__name__)

_STYLE_CN: dict[StyleType, str] = {
    StyleType.popular_science: "入门科普",
    StyleType.practical_guide: "实战操作",
    StyleType.reference_tool: "工具手册",
    StyleType.insight_opinion: "观念洞察",
    StyleType.textbook: "教科书",
    StyleType.technical_deep_dive: "技术深度分析",
    StyleType.ai_review_commentary: "评估评论",
}


def narrative_kind_for_style(style_type: str | StyleType | None) -> Literal["A", "B", "C"]:
    if isinstance(style_type, StyleType):
        st = style_type
    elif isinstance(style_type, str) and style_type.strip():
        try:
            st = StyleType(style_type)
        except ValueError:
            st = StyleType.popular_science
    else:
        st = StyleType.popular_science
    if st in (StyleType.reference_tool, StyleType.textbook, StyleType.technical_deep_dive):
        return "B"
    if st == StyleType.practical_guide:
        return "C"
    return "A"


class NarrativeAgent:
    def __init__(self) -> None:
        self._client = LLMClient()

    def _system_prompt(self, kind: Literal["A", "B", "C"]) -> str:
        if kind == "B":
            return NARRATIVE_SYSTEM_B
        if kind == "C":
            return NARRATIVE_SYSTEM_C
        return NARRATIVE_SYSTEM_A

    def _user_message(self, book: Book, outline_markdown: str, chapter_count: int, kind: Literal["A", "B", "C"]) -> str:
        st = coerce_style(book.book_type.value, book.style_type)
        label = _STYLE_CN.get(st, "入门科普")
        title = (book.title or "").strip() or "未命名书稿"
        parts = [
            "以下是策划输入。请严格按系统指令输出宪法全文（不要输出任何前言或后记）。",
            "",
            f"- 书名：{title}",
        ]
        if kind != "C":
            parts.append(f"- 书型：{label}")
        parts.append("")
        parts.append("- 完整大纲：")
        parts.append(outline_markdown.strip() or "（空）")
        parts.append("")
        if kind != "B":
            parts.append(f"- 总章数：{chapter_count}")
        return "\n".join(parts)

    def generate_constitution(
        self,
        book: Book,
        outline_markdown: str,
        *,
        chapter_count: int,
        model: str | None = None,
        max_tokens: int = 12000,
    ) -> str:
        kind = narrative_kind_for_style(book.style_type)
        system = self._system_prompt(kind)
        user_msg = self._user_message(book, outline_markdown, chapter_count, kind)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]
        out = self._client.chat_completion(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=0.55,
            disable_thinking=True,
        )
        text = out.strip()
        if not text and max_tokens < 24000:
            retry_tokens = min(max(max_tokens * 2, max_tokens + 4096), 24000)
            logger.warning(
                "narrative constitution empty for book %s; retrying with max_tokens=%s",
                book.id,
                retry_tokens,
            )
            text = self._client.chat_completion(
                messages,
                model=model,
                max_tokens=retry_tokens,
                temperature=0.55,
                disable_thinking=True,
            ).strip()
        if not text:
            logger.warning(
                "narrative constitution empty for book %s; retrying with direct-output instruction",
                book.id,
            )
            retry_messages = [
                *messages,
                {
                    "role": "user",
                    "content": "上次未返回正文。请直接输出叙事/体例宪法全文，不要输出思考过程，必须以 --- 或 # 开头。",
                },
            ]
            text = self._client.chat_completion(
                retry_messages,
                model=model,
                max_tokens=24000,
                temperature=0.55,
                disable_thinking=True,
            ).strip()
        if not text:
            logger.warning("narrative constitution empty for book %s", book.id)
        return text
