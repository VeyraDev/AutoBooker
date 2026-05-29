"""书籍向图像 Prompt 构建。"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.llm.client import LLMClient
from app.services.figure_render.figure_ai import STYLE_MAP

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "prompts" / "figure_types"


def _load_template(name: str) -> str:
    path = _TEMPLATES_DIR / f"{name}.txt"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return "专业书籍插图。{description}"


def classify_figure_sub_kind(description: str, hint: str = "") -> str:
    h = (hint or "").strip().lower()
    if h in (
        "architecture",
        "concept_diagram",
        "illustration",
        "infographic",
        "scene_illustration",
        "chapter_summary",
    ):
        if h == "illustration":
            return "scene_illustration"
        if h == "chapter_summary":
            return "infographic"
        return h
    d = (description or "").casefold()
    if any(k in d for k in ("架构", "模块", "系统", "部署", "agent")):
        return "architecture"
    if any(k in d for k in ("信息图", "总结", "对比")):
        return "infographic"
    if any(k in d for k in ("场景", "氛围", "人物")):
        return "scene_illustration"
    return "concept_diagram"


def build_figure_prompt_from_template(
    description: str,
    style_type: str,
    *,
    sub_kind: str = "concept_diagram",
) -> str:
    sk = classify_figure_sub_kind(description, sub_kind)
    if sk == "architecture":
        return f"ARCHITECTURE_GRAPHVIZ:{description}"

    template_name = sk if sk != "illustration" else "scene_illustration"
    tpl = _load_template(template_name)
    style_hint = STYLE_MAP.get(style_type, "专业出版插图风格")
    prompt = tpl.format(description=description.strip(), style_hint=style_hint)
    return prompt


def llm_expand_image_prompt(description: str, style_type: str, sub_kind: str) -> str:
    """可选 LLM 扩写（轻量）。"""
    base = build_figure_prompt_from_template(description, style_type, sub_kind=sub_kind)
    if base.startswith("ARCHITECTURE_GRAPHVIZ:"):
        return base
    try:
        client = LLMClient()
        out = client.chat_completion(
            [
                {
                    "role": "user",
                    "content": f"将下列图像需求扩写为中文图像生成提示词（一段，无 markdown，描述画面内容与风格）：\n{base}",
                }
            ],
            model=settings.intent_model,
            max_tokens=400,
            temperature=0.3,
        )
        return (out or base).strip()
    except Exception as e:
        logger.warning("figure prompt expand failed: %s", e)
        return base
