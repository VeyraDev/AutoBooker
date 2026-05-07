"""Stream chapter body via DeepSeek（若配置）或 DashScope。"""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.config import settings
from app.llm.client import AsyncLLMClient
from app.prompts.chapter_writer import WRITER_SYSTEM_PROMPT


class ChapterWriterAgent:
    def __init__(self) -> None:
        self._client = AsyncLLMClient()

    async def stream(
        self,
        chapter: dict[str, Any],
        book_memory: dict[str, Any],
        reference_snippets: list[str],
        *,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        system = WRITER_SYSTEM_PROMPT.format(
            book_type=book_memory["book_type"],
            style_guide=book_memory.get("style_guide", "流畅自然，逻辑清晰"),
            citation_style=book_memory.get("citation_style", "无"),
            term_glossary=str(book_memory.get("terms", {})),
            prev_chapter_summary=book_memory.get("prev_summary", "无"),
            next_chapter_summary=book_memory.get("next_summary", "无"),
            target_words=chapter.get("estimated_words", 3000),
        )
        user_msg = self._build_user_message(chapter, reference_snippets)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]
        async for token in self._client.stream_chat(
            messages,
            model=model,
            max_tokens=8192,
            temperature=0.75,
            provider="writer",
        ):
            yield token

    def _build_user_message(self, chapter: dict[str, Any], snippets: list[str]) -> str:
        parts = [
            f"章节标题：{chapter['title']}",
            f"本章摘要：{chapter.get('summary', '')}",
            f"核心论点：{'; '.join(chapter.get('key_points', []))}",
        ]
        if snippets:
            parts.append("参考资料：")
            parts.extend([f"- {s[:300]}..." if len(s) > 300 else f"- {s}" for s in snippets])
        parts.append("请开始写作：")
        return "\n".join(parts)
