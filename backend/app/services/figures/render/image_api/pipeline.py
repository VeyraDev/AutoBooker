"""FIGURE 插图管道：提示词构建 + 按配置路由到智灵/OpenAI Images 或通义万相。"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from openai import APIConnectionError, APITimeoutError

from app.config import settings
from app.services.figures.render.image_api.prompt_constraints import (
    build_direct_fallback_prompt,
    build_layoutscript_image_prompt,
    build_no_layout_image_prompt,
)

logger = logging.getLogger(__name__)


def resolve_figure_prompt_mode(prompt_mode: str | None = None) -> str:
    mode = (prompt_mode or settings.FIGURE_PROMPT_MODE or "no_layout").strip().lower()
    return mode if mode in {"no_layout", "full_v3"} else "no_layout"


def build_figure_prompt(
    description: str,
    style_type: str,
    *,
    sub_kind: str = "figure",
    layout_script: str | None = None,
    prompt_mode: str | None = None,
) -> str:
    _ = style_type
    mode = resolve_figure_prompt_mode(prompt_mode)
    if mode == "full_v3" and layout_script and layout_script.strip():
        return build_layoutscript_image_prompt(layout_script, sub_kind or "concept_diagram")
    if mode == "no_layout":
        return build_no_layout_image_prompt(description, sub_kind or "concept_diagram")
    if layout_script and layout_script.strip():
        return build_layoutscript_image_prompt(layout_script, sub_kind or "concept_diagram")
    return build_direct_fallback_prompt(description, sub_kind or "concept_diagram")


def resolve_figure_image_provider() -> str:
    """zeelin | openai | wanx；FIGURE_IMAGE_PROVIDER=auto 时优先智灵网关。"""
    p = (settings.FIGURE_IMAGE_PROVIDER or "auto").strip().lower()
    if p == "zeelin":
        return "zeelin"
    if p == "openai":
        return "openai"
    if p == "wanx":
        return "wanx"
    if settings.ZEELIN_API_KEY.strip():
        return "zeelin"
    if settings.OPENAI_API_KEY.strip():
        return "openai"
    if settings.DASHSCOPE_API_KEY.strip():
        return "wanx"
    return "openai"


def _wanx_fallback_enabled() -> bool:
    if not settings.DASHSCOPE_API_KEY.strip():
        return False
    if not settings.FIGURE_IMAGE_FALLBACK_WANX:
        return False
    return resolve_figure_image_provider() != "wanx"


def _is_openai_transient(err: BaseException) -> bool:
    if isinstance(err, (APITimeoutError, APIConnectionError, httpx.TimeoutException, httpx.ConnectError)):
        return True
    msg = str(err).lower()
    return "timeout" in msg or "timed out" in msg or "connect" in msg


def _should_fallback_to_wanx(err: BaseException) -> bool:
    """网络/超时/配额/欠费等不可恢复于同一 provider 的错误，尝试万相。"""
    if _is_openai_transient(err):
        return True
    msg = str(err).lower()
    return any(
        token in msg
        for token in (
            "billing",
            "hard limit",
            "insufficient_quota",
            "quota",
            "exceeded your current quota",
            "rate limit",
            "余额不足",
            "欠费",
        )
    )


def generate_figure_image(
    description: str,
    output_path: Path,
    *,
    style_type: str = "",
    sub_kind: str = "figure",
    layout_script: str | None = None,
    prompt_mode: str | None = None,
) -> tuple[str, Path]:
    provider = resolve_figure_image_provider()
    logger.info("figure image provider=%s", provider)

    if provider in {"zeelin", "openai"}:
        from app.services.figures.render.image_api.wanx_provider import generate_figure_image_wanx
        if provider == "zeelin":
            from app.services.figures.render.image_api.zeelin_provider import generate_figure_image_zeelin

            generator = generate_figure_image_zeelin
        else:
            from app.services.figures.render.image_api.openai_provider import generate_figure_image_openai

            generator = generate_figure_image_openai

        try:
            return generator(
                description,
                output_path,
                style_type=style_type,
                sub_kind=sub_kind,
                layout_script=layout_script,
                prompt_mode=prompt_mode,
            )
        except Exception as e:
            if _wanx_fallback_enabled() and _should_fallback_to_wanx(e):
                logger.warning("%s 插图失败，回退万相: %s", provider, e)
                return generate_figure_image_wanx(
                    description,
                    output_path,
                    style_type=style_type,
                    sub_kind=sub_kind,
                    layout_script=layout_script,
                    prompt_mode=prompt_mode,
                )
            raise

    from app.services.figures.render.image_api.wanx_provider import generate_figure_image_wanx

    return generate_figure_image_wanx(
        description,
        output_path,
        style_type=style_type,
        sub_kind=sub_kind,
        layout_script=layout_script,
        prompt_mode=prompt_mode,
    )
