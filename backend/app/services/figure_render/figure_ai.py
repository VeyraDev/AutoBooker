"""FIGURE 插图管道：提示词构建 + 按配置路由到 OpenAI Images 或通义万相。"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from openai import APIConnectionError, APITimeoutError

from app.config import settings

logger = logging.getLogger(__name__)

FIGURE_STYLE_PREFIX = """
技术插图，简洁矢量风格，
扁平设计，蓝白配色（#1B4F72 与 #EBF5FB），
图中无文字、无字母、无数字、无标签、无货币符号，
专业出版品质，与全书其他插图风格一致。
""".strip()

STYLE_MAP = {
    "textbook": "学术教材插图风格，精确简洁",
    "popular_science": "现代信息图风格，亲和明快",
    "practical_guide": "技术图解风格，步骤清晰",
    "入门科普": "现代信息图风格，亲和明快",
    "技术深度分析": "学术技术插图，精确严谨",
    "实战操作": "分步技术图解",
    "教科书": "学术教材插图风格",
}

ARCHITECTURE_SUFFIX = (
    "系统架构示意图，抽象几何块与箭头，"
    "无可读文字与标签，无货币符号，线条简洁，专业风格。"
)
ILLUSTRATION_SUFFIX = "场景插图，扁平设计，亲和易懂，图中无文字。"


def build_figure_prompt(
    description: str,
    style_type: str,
    *,
    sub_kind: str = "figure",
) -> str:
    style_prefix = STYLE_MAP.get(style_type, "专业出版插图风格")
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
