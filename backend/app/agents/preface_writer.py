"""Stream preface body via LLM."""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.llm.client import AsyncLLMClient
from app.prompts.preface_writer import PREFACE_WRITER_SYSTEM


class PrefaceWriterAgent:
    def __init__(self) -> None:
        self._client = AsyncLLMClient()

    async def stream(
        self,
        *,
        book_title: str,
        brief: str,
        narrative_constitution: str,
        target_words: int,
        book_type: str,
        model: str | None = None,
        temperature: float = 0.75,
    ) -> AsyncIterator[str]:
        system = PREFACE_WRITER_SYSTEM.format(target_words=target_words)
        user = "\n".join(
            [
                f"书名：{book_title}",
                f"类型：{book_type}",
                f"前言要点：{brief or '（由全书主题自然展开）'}",
                "叙事宪法摘录：",
                (narrative_constitution or "")[:4000],
            ]
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        async for token in self._client.stream_chat(
            messages,
            model=model,
            max_tokens=8192,
            temperature=temperature,
        ):
            yield token
