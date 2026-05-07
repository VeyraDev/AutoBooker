"""DashScope：向量嵌入；DeepSeek（可选）：大纲与章节流式写作。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Literal

from openai import APIError, AsyncOpenAI, OpenAI, RateLimitError

from app.config import settings

logger = logging.getLogger(__name__)


def _backoff_sleep(attempt: int) -> None:
    delay = settings.LLM_RETRY_BASE_SECONDS * (2**attempt)
    time.sleep(delay)


ChatProvider = Literal["writer", "dashscope"]


class LLMClient:
    """Sync：嵌入始终 DashScope；chat 可选 DeepSeek（writer）或 DashScope（记忆抽取等）。"""

    def __init__(self) -> None:
        self._dashscope = OpenAI(
            api_key=settings.DASHSCOPE_API_KEY or None,
            base_url=settings.DASHSCOPE_BASE_URL,
        )
        if settings.use_deepseek_writer():
            self._writer_chat = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
        else:
            self._writer_chat = self._dashscope

    def embed(self, texts: list[str]) -> list[list[float]]:
        """DashScope embedding（与向量检索一致）。"""
        if not texts:
            return []
        batch_size = min(settings.EMBEDDING_BATCH_SIZE, 25)
        out: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            last_err: Exception | None = None
            for attempt in range(settings.LLM_MAX_RETRIES):
                try:
                    resp = self._dashscope.embeddings.create(
                        model=settings.EMBEDDING_MODEL,
                        input=batch,
                        dimensions=settings.EMBEDDING_DIMENSIONS,
                        encoding_format="float",
                    )
                    out.extend([d.embedding for d in resp.data])
                    break
                except (APIError, RateLimitError, TimeoutError) as e:
                    last_err = e
                    logger.warning("embed attempt %s failed: %s", attempt + 1, e)
                    if attempt < settings.LLM_MAX_RETRIES - 1:
                        _backoff_sleep(attempt)
            else:
                if last_err:
                    raise last_err
                raise RuntimeError("embedding failed with no error recorded")
        return out

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        provider: ChatProvider = "writer",
    ) -> str:
        if provider == "dashscope":
            client = self._dashscope
            m = model or settings.CHAT_MODEL_FAST
        else:
            client = self._writer_chat
            m = model or settings.default_writer_model()
        last_err: Exception | None = None
        for attempt in range(settings.LLM_MAX_RETRIES):
            try:
                resp = client.chat.completions.create(
                    model=m,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                choice = resp.choices[0].message
                return (choice.content or "").strip()
            except (APIError, RateLimitError, TimeoutError) as e:
                last_err = e
                logger.warning("chat_completion attempt %s failed: %s", attempt + 1, e)
                if attempt < settings.LLM_MAX_RETRIES - 1:
                    _backoff_sleep(attempt)
        if last_err:
            raise last_err
        raise RuntimeError("chat_completion failed with no error recorded")


class AsyncLLMClient:
    """异步流式：章节写作走 DeepSeek（若配置），否则 DashScope。"""

    def __init__(self) -> None:
        self._dashscope = AsyncOpenAI(
            api_key=settings.DASHSCOPE_API_KEY or None,
            base_url=settings.DASHSCOPE_BASE_URL,
        )
        if settings.use_deepseek_writer():
            self._writer_chat = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
        else:
            self._writer_chat = self._dashscope

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        provider: ChatProvider = "writer",
    ) -> AsyncIterator[str]:
        client = self._dashscope if provider == "dashscope" else self._writer_chat
        m = (
            model
            or (settings.CHAT_MODEL_FAST if provider == "dashscope" else settings.default_writer_model())
        )
        last_err: Exception | None = None
        for attempt in range(settings.LLM_MAX_RETRIES):
            try:
                stream = await client.chat.completions.create(
                    model=m,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
                return
            except (APIError, RateLimitError, TimeoutError) as e:
                last_err = e
                logger.warning("stream_chat attempt %s failed: %s", attempt + 1, e)
                if attempt < settings.LLM_MAX_RETRIES - 1:
                    await asyncio.sleep(settings.LLM_RETRY_BASE_SECONDS * (2**attempt))
        if last_err:
            raise last_err
        raise RuntimeError("stream_chat failed with no error recorded")
