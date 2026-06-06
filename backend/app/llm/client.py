"""多服务商 LLM 客户端：OpenAI 兼容 + Claude（Anthropic）。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator

from anthropic import APIError as AnthropicAPIError
from anthropic import Anthropic, AsyncAnthropic
from anthropic import RateLimitError as AnthropicRateLimitError
from openai import APIError, AsyncOpenAI, OpenAI, RateLimitError

from app.config import settings
from app.llm.providers import (
    is_provider_configured,
    parse_ai_model,
    provider_api_key,
    provider_base_url,
)

logger = logging.getLogger(__name__)


def _backoff_sleep(attempt: int) -> None:
    delay = settings.LLM_RETRY_BASE_SECONDS * (2**attempt)
    time.sleep(delay)


def _resolve_target(model: str | None) -> tuple[str, str]:
    provider_id, model_name = parse_ai_model(model)
    if not is_provider_configured(provider_id):
        raise RuntimeError(f"LLM provider '{provider_id}' is not configured (missing API key)")
    return provider_id, model_name


def _fallback_targets(primary_provider: str, model: str | None) -> list[tuple[str, str]]:
    """主服务商失败时，若 DeepSeek 已配置且主服务商非 DeepSeek，则回退 DeepSeek。"""
    targets = [_resolve_target(model)]
    if primary_provider != "deepseek" and is_provider_configured("deepseek"):
        fallback_model = settings.DEEPSEEK_CHAT_MODEL
        if model and ":" not in (model or ""):
            _, parsed = parse_ai_model(model)
            if parsed.startswith("deepseek-"):
                fallback_model = parsed
        targets.append(("deepseek", fallback_model))
    return targets


def _split_messages_for_anthropic(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    conv: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            if isinstance(content, str) and content.strip():
                system_parts.append(content.strip())
            continue
        if role in ("user", "assistant"):
            conv.append({"role": role, "content": content if isinstance(content, str) else str(content)})
    system = "\n\n".join(system_parts) if system_parts else None
    return system, conv


class LLMClient:
    """同步：嵌入走千问 DashScope；对话按 provider:model 路由。"""

    def __init__(self) -> None:
        self._openai_clients: dict[str, OpenAI] = {}
        self._anthropic: Anthropic | None = None

    def _get_openai(self, provider_id: str) -> OpenAI:
        if provider_id not in self._openai_clients:
            self._openai_clients[provider_id] = OpenAI(
                api_key=provider_api_key(provider_id) or None,
                base_url=provider_base_url(provider_id),
            )
        return self._openai_clients[provider_id]

    def _get_anthropic(self) -> Anthropic:
        if self._anthropic is None:
            self._anthropic = Anthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                base_url=settings.ANTHROPIC_BASE_URL or None,
            )
        return self._anthropic

    def _dashscope_embed_client(self) -> OpenAI:
        return self._get_openai("qwen")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """DashScope 向量嵌入（与检索一致，始终走千问）。"""
        if not texts:
            return []
        if not is_provider_configured("qwen"):
            raise RuntimeError("DASHSCOPE_API_KEY is required for embeddings")
        batch_size = min(settings.EMBEDDING_BATCH_SIZE, 25)
        client = self._dashscope_embed_client()
        out: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            last_err: Exception | None = None
            for attempt in range(settings.LLM_MAX_RETRIES):
                try:
                    resp = client.embeddings.create(
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

    @staticmethod
    def _openai_uses_max_completion_tokens(model_name: str) -> bool:
        m = model_name.lower()
        return m.startswith(("gpt-5", "o1", "o3", "o4"))

    def _chat_openai(
        self,
        client: OpenAI,
        model_name: str,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if self._openai_uses_max_completion_tokens(model_name):
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message
        return (choice.content or "").strip()

    def _chat_anthropic(
        self,
        model_name: str,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        system, conv = _split_messages_for_anthropic(messages)
        if not conv:
            conv = [{"role": "user", "content": ""}]
        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": conv,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        resp = self._get_anthropic().messages.create(**kwargs)
        parts = [getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip()

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        primary_provider, _ = parse_ai_model(model)
        specs = _fallback_targets(primary_provider, model)
        last_outer: Exception | None = None

        for idx, (provider_id, model_name) in enumerate(specs):
            last_err: Exception | None = None
            for attempt in range(settings.LLM_MAX_RETRIES):
                try:
                    if provider_id == "claude":
                        return self._chat_anthropic(
                            model_name,
                            messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                    client = self._get_openai(provider_id)
                    return self._chat_openai(
                        client,
                        model_name,
                        messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                except (APIError, RateLimitError, TimeoutError, AnthropicAPIError, AnthropicRateLimitError) as e:
                    last_err = e
                    logger.warning(
                        "chat_completion attempt %s (%s:%s) failed: %s",
                        attempt + 1,
                        provider_id,
                        model_name,
                        e,
                    )
                    if attempt < settings.LLM_MAX_RETRIES - 1:
                        _backoff_sleep(attempt)
            last_outer = last_err
            if idx < len(specs) - 1 and last_err is not None:
                logger.warning(
                    "chat_completion switching to deepseek fallback after %s:%s failure: %s",
                    provider_id,
                    model_name,
                    last_err,
                )
        if last_outer:
            raise last_outer
        raise RuntimeError("chat_completion failed with no error recorded")


class AsyncLLMClient:
    """异步流式：按 provider:model 路由。"""

    def __init__(self) -> None:
        self._openai_clients: dict[str, AsyncOpenAI] = {}
        self._anthropic: AsyncAnthropic | None = None

    def _get_openai(self, provider_id: str) -> AsyncOpenAI:
        if provider_id not in self._openai_clients:
            self._openai_clients[provider_id] = AsyncOpenAI(
                api_key=provider_api_key(provider_id) or None,
                base_url=provider_base_url(provider_id),
            )
        return self._openai_clients[provider_id]

    def _get_anthropic(self) -> AsyncAnthropic:
        if self._anthropic is None:
            self._anthropic = AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                base_url=settings.ANTHROPIC_BASE_URL or None,
            )
        return self._anthropic

    async def _stream_openai(
        self,
        client: AsyncOpenAI,
        model_name: str,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        stream = await client.chat.completions.create(
            model=model_name,
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

    async def _stream_anthropic(
        self,
        model_name: str,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        system, conv = _split_messages_for_anthropic(messages)
        if not conv:
            conv = [{"role": "user", "content": ""}]
        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": conv,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        async with self._get_anthropic().messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        primary_provider, _ = parse_ai_model(model)
        specs = _fallback_targets(primary_provider, model)
        last_outer: Exception | None = None

        for idx, (provider_id, model_name) in enumerate(specs):
            last_err: Exception | None = None
            for attempt in range(settings.LLM_MAX_RETRIES):
                try:
                    if provider_id == "claude":
                        async for token in self._stream_anthropic(
                            model_name,
                            messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ):
                            yield token
                    else:
                        client = self._get_openai(provider_id)
                        async for token in self._stream_openai(
                            client,
                            model_name,
                            messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ):
                            yield token
                    return
                except (APIError, RateLimitError, TimeoutError, AnthropicAPIError, AnthropicRateLimitError) as e:
                    last_err = e
                    logger.warning(
                        "stream_chat attempt %s (%s:%s) failed: %s",
                        attempt + 1,
                        provider_id,
                        model_name,
                        e,
                    )
                    if attempt < settings.LLM_MAX_RETRIES - 1:
                        await asyncio.sleep(settings.LLM_RETRY_BASE_SECONDS * (2**attempt))
            last_outer = last_err
            if idx < len(specs) - 1 and last_err is not None:
                logger.warning(
                    "stream_chat switching to deepseek fallback after %s:%s failure: %s",
                    provider_id,
                    model_name,
                    last_err,
                )
        if last_outer:
            raise last_outer
        raise RuntimeError("stream_chat failed with no error recorded")
