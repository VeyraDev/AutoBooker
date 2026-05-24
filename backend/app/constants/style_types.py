"""二级体裁（style_type）与一级书类（book_type）的约束。"""

from __future__ import annotations

import enum


class StyleType(str, enum.Enum):
    popular_science = "popular_science"  # 入门科普
    practical_guide = "practical_guide"  # 实战操作
    reference_tool = "reference_tool"  # 工具手册
    insight_opinion = "insight_opinion"  # 观念洞察
    textbook = "textbook"  # 教科书
    technical_deep_dive = "technical_deep_dive"  # 技术深度分析
    ai_review_commentary = "ai_review_commentary"  # 评估评论


NONFICTION_STYLES: frozenset[StyleType] = frozenset(
    {
        StyleType.popular_science,
        StyleType.practical_guide,
        StyleType.reference_tool,
        StyleType.insight_opinion,
    }
)

ACADEMIC_STYLES: frozenset[StyleType] = frozenset(
    {
        StyleType.textbook,
        StyleType.technical_deep_dive,
        StyleType.ai_review_commentary,
    }
)

# 与 prompts/styles 下文件名对应（不含路径）
STYLE_PROMPT_BASENAME: dict[StyleType, str] = {
    StyleType.popular_science: "outline_prompt_入门科普",
    StyleType.practical_guide: "outline_prompt_实战操作",
    StyleType.reference_tool: "outline_prompt_工具手册",
    StyleType.insight_opinion: "outline_prompt_观念洞察",
    StyleType.textbook: "outline_prompt_教科书",
    StyleType.technical_deep_dive: "outline_prompt_技术深度分析",
    StyleType.ai_review_commentary: "outline_prompt_评估评论",
}

DEFAULT_TARGET_WORDS: dict[str, int] = {
    "nonfiction": 80_000,
    "academic": 200_000,
}

TOPIC_TAG_PRESETS: list[str] = [
    "AI Agent",
    "OpenClaw",
    "AI编程",
    "一人公司",
    "AI教育",
    "LLM",
    "AI创业",
    "AI哲学",
    "短视频",
    "Coze",
    "RAG",
    "MCP",
]


def allowed_styles_for_book_type(book_type: str) -> list[StyleType]:
    if book_type == "academic":
        return sorted(ACADEMIC_STYLES, key=lambda s: s.value)
    return sorted(NONFICTION_STYLES, key=lambda s: s.value)


def default_style_for_book_type(book_type: str) -> StyleType:
    if book_type == "academic":
        return StyleType.textbook
    return StyleType.popular_science


def coerce_style(book_type: str, style: StyleType | str | None) -> StyleType:
    if style is None:
        return default_style_for_book_type(book_type)
    if isinstance(style, StyleType):
        st = style
    else:
        try:
            st = StyleType(style)
        except ValueError:
            return default_style_for_book_type(book_type)
    allowed = allowed_styles_for_book_type(book_type)
    return st if st in allowed else default_style_for_book_type(book_type)
