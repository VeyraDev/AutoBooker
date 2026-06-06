"""FIGURE 插图管道：提示词构建 + 按配置路由到 OpenAI Images 或通义万相。"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from openai import APIConnectionError, APITimeoutError

from app.config import settings

logger = logging.getLogger(__name__)

BASE_BOOK_STYLE = """
书籍内页配图，克制的编辑插图风格，白色或浅色背景，简洁矢量线条，
低饱和蓝灰配色，留白充足，非海报，非广告，非照片写实，适合专业中文书稿。
""".strip()

STYLE_MAP = {
    "textbook": "学术教材插图风格，精确简洁",
    "popular_science": "现代科普插图风格，亲和明快",
    "practical_guide": "技术图解风格，步骤清晰",
    "入门科普": "现代科普插图风格，亲和明快",
    "技术深度分析": "学术技术插图，精确严谨",
    "实战操作": "分步技术图解",
    "教科书": "学术教材插图风格",
}

SUB_KIND_SUFFIX = {
    "scene_illustration": "具象场景插图，只表现人物、环境和氛围；横向 4:3 或 16:9 内页构图；不要可读文字、标签、数字、UI 截图或复杂图表。",
    "case_scene": "案例场景插图，表现真实使用情境；横向 4:3 内页构图；不要可读文字、标签、数字和海报式大标题。",
    "future_scene": "未来感场景插图，专业克制，横向留白构图；不要赛博朋克海报，不要文字。",
    "human_ai_scene": "人机协作场景插图，强调协作关系和空间氛围，横向内页构图，不要文字。",
    "infographic": "信息图风格只用于装饰性概览；不要生成长文字，最多出现抽象短标签占位，避免乱码。",
    "concept_diagram": "概念视觉化图解，使用统一色块、少量清晰大标签和简洁图标；标签不超过 6 个，每个标签 2-6 个字，避免细小文字和密集说明。",
    "architecture": "结构视觉化图解，使用统一蓝灰色块、清晰分层、少量大标签和简洁图标；标签不超过 8 个，每个标签 2-8 个字，保持充足间距，避免乱码和长句。",
    "process_flow": "流程视觉化图解，使用统一蓝灰色块、清晰箭头、少量大标签和简洁图标；每步一个短标签，不要把说明文字写入节点。",
    "comparison_matrix": "对比视觉化图解，使用整齐表格或卡片矩阵、统一色块和简洁图标；只保留短对象名和短维度名，避免长段文字。",
}


def build_figure_prompt(
    description: str,
    style_type: str,
    *,
    sub_kind: str = "figure",
) -> str:
    style_prefix = STYLE_MAP.get(style_type, "专业出版插图风格")
    kind = (sub_kind or "scene_illustration").strip().lower()
    suffix = SUB_KIND_SUFFIX.get(kind, SUB_KIND_SUFFIX["scene_illustration"])
    return f"{style_prefix}。{BASE_BOOK_STYLE}。{suffix}\n画面需求：{description.strip()}"


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
