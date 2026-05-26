"""FIGURE 插图管道：提示词构建 + 按配置路由到 OpenAI Images 或通义万相。"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from openai import APIConnectionError, APITimeoutError

from app.config import settings

logger = logging.getLogger(__name__)

FIGURE_STYLE_PREFIX = """
Technical illustration, clean vector style,
flat design, blue and white color scheme (#1B4F72 and #EBF5FB),
no text, no letters, no numbers, no labels, no dollar signs, no currency symbols,
no mathematical glyphs, professional publishing quality,
consistent with other figures in the same book.
""".strip()

STYLE_MAP = {
    "textbook": "Academic textbook illustration style, precise and clean",
    "popular_science": "Modern infographic style, approachable and colorful",
    "practical_guide": "Technical diagram style, step-by-step clarity",
    "入门科普": "Modern infographic style, approachable and colorful",
    "技术深度分析": "Academic technical illustration, precise",
    "实战操作": "Step-by-step technical diagram",
    "教科书": "Academic textbook illustration style",
}

ARCHITECTURE_SUFFIX = (
    "Technical architecture diagram, abstract geometric blocks and arrows only, "
    "no readable text, no labels, no dollar or currency symbols, clean lines, professional."
)
ILLUSTRATION_SUFFIX = "Scene illustration, flat design, approachable, no text in image."


def build_figure_prompt(
    description: str,
    style_type: str,
    *,
    sub_kind: str = "figure",
) -> str:
    style_prefix = STYLE_MAP.get(style_type, "Professional publishing illustration")
    suffix = ARCHITECTURE_SUFFIX if sub_kind == "architecture" else ILLUSTRATION_SUFFIX
    return f"{style_prefix}. {FIGURE_STYLE_PREFIX}. {suffix}. {description}"


def resolve_figure_image_provider() -> str:
    """openai | wanx；FIGURE_IMAGE_PROVIDER=auto 时优先 OpenAI。"""
    p = (settings.FIGURE_IMAGE_PROVIDER or "auto").strip().lower()
    if p == "openai":
        return "openai"
    if p == "wanx":
        return "wanx"
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


def generate_figure_image(
    description: str,
    output_path: Path,
    *,
    style_type: str = "",
    sub_kind: str = "figure",
) -> tuple[str, Path]:
    provider = resolve_figure_image_provider()
    logger.info("figure image provider=%s", provider)

    if provider == "openai":
        from app.services.figure_render.figure_openai import generate_figure_image_openai
        from app.services.figure_render.figure_wanx import generate_figure_image_wanx

        try:
            return generate_figure_image_openai(
                description,
                output_path,
                style_type=style_type,
                sub_kind=sub_kind,
            )
        except Exception as e:
            if _wanx_fallback_enabled() and _is_openai_transient(e):
                logger.warning("OpenAI 插图失败，回退万相: %s", e)
                return generate_figure_image_wanx(
                    description,
                    output_path,
                    style_type=style_type,
                    sub_kind=sub_kind,
                )
            raise

    from app.services.figure_render.figure_wanx import generate_figure_image_wanx

    return generate_figure_image_wanx(
        description,
        output_path,
        style_type=style_type,
        sub_kind=sub_kind,
    )
