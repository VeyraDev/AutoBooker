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
        constitution = (book_memory.get("narrative_constitution") or "").strip() or "（未生成叙事宪法，请按体裁常识写作。）"
        system = WRITER_SYSTEM_PROMPT.format(
            book_type=book_memory["book_type"],
            narrative_constitution=constitution,
            style_examples=book_memory.get("style_examples", ""),
            chapter_index=chapter.get("chapter_index", 1),
            total_chapters=chapter.get("total_chapters", 1),
            chapter_title=chapter.get("title", ""),
            prev_chapter_hook=book_memory.get("prev_chapter_hook", "无"),
            style_voice_block=book_memory.get("style_voice_block", ""),
            topic_tags_line=book_memory.get("topic_tags_line", "（未选标签）"),
            user_material=book_memory.get("user_material", "（无）"),
            style_guide=book_memory.get("style_guide", "流畅自然，逻辑清晰"),
            citation_style=book_memory.get("citation_style", "无"),
            term_glossary=str(book_memory.get("terms", {})),
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
            f"本章摘要：{chapter.get('summary', '')}",
            f"核心论点：{'; '.join(chapter.get('key_points', []))}",
        ]
        if snippets:
            parts.append("参考资料：")
            parts.extend([f"- {s[:300]}..." if len(s) > 300 else f"- {s}" for s in snippets])
        parts.append(
            "请直接输出本章正文（可使用 Markdown 标题与列表）。"
            "不要写开场套话或与读者对话的句子；不要复述任务说明。"
        )
        return "\n".join(parts)
