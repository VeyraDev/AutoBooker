"""按体裁（style_type）决定文献检索数据源与配额。"""

from __future__ import annotations

from dataclasses import dataclass

from app.constants.style_types import StyleType

PROFILE_PRACTICAL = "practical"
PROFILE_POPULAR = "popular"
PROFILE_ACADEMIC = "academic"
PROFILE_TECHNICAL = "technical"

# 兼容旧 profile 名
PROFILE_NONFICTION = PROFILE_POPULAR
PROFILE_TECHNICAL_LEGACY = PROFILE_TECHNICAL

SOURCE_LABELS: dict[str, str] = {
    "wikipedia": "维基百科",
    "crossref": "CrossRef",
    "semantic_scholar": "Semantic Scholar",
    "arxiv": "arXiv",
    "github": "GitHub",
    "official_doc": "官方文档",
}


@dataclass(frozen=True)
class SourceQuota:
    github: int = 0
    official_doc: int = 0
    wikipedia: int = 0
    papers: int = 0  # arxiv + ss + crossref 合计上限


def literature_profile(book_type: str, style_type: str | None) -> str:
    st = (style_type or "").strip()
    if st in (StyleType.practical_guide.value, StyleType.reference_tool.value):
        return PROFILE_PRACTICAL
    if st in (StyleType.popular_science.value, StyleType.insight_opinion.value):
        return PROFILE_POPULAR
    if st in (
        StyleType.textbook.value,
        StyleType.technical_deep_dive.value,
        StyleType.ai_review_commentary.value,
    ):
        return PROFILE_ACADEMIC
    if book_type == "academic":
        return PROFILE_ACADEMIC
    return PROFILE_POPULAR


def source_quota(profile: str, total_rows: int = 25) -> SourceQuota:
    """按 profile 分配各 Tab 条数（合计约 total_rows）。"""
    if profile == PROFILE_PRACTICAL:
        return SourceQuota(
            github=max(4, int(total_rows * 0.4)),
            official_doc=max(3, int(total_rows * 0.3)),
            wikipedia=max(2, int(total_rows * 0.2)),
            papers=max(2, int(total_rows * 0.1)),
        )
    if profile == PROFILE_POPULAR:
        return SourceQuota(
            wikipedia=max(4, int(total_rows * 0.35)),
            papers=max(6, int(total_rows * 0.45)),
            github=max(2, int(total_rows * 0.1)),
            official_doc=max(1, int(total_rows * 0.1)),
        )
    if profile == PROFILE_TECHNICAL:
        return SourceQuota(
            github=max(4, int(total_rows * 0.35)),
            papers=max(8, int(total_rows * 0.5)),
            wikipedia=max(2, int(total_rows * 0.1)),
            official_doc=max(2, int(total_rows * 0.05)),
        )
    # academic / textbook
    return SourceQuota(
        papers=max(10, int(total_rows * 0.7)),
        github=max(3, int(total_rows * 0.2)),
        wikipedia=max(2, int(total_rows * 0.05)),
        official_doc=max(1, int(total_rows * 0.05)),
    )


def profile_source_hint(profile: str) -> str:
    if profile == PROFILE_PRACTICAL:
        return "GitHub · 官方文档 · 维基百科 · 论文"
    if profile == PROFILE_POPULAR:
        return "维基百科 · 论文 · GitHub"
    if profile == PROFILE_TECHNICAL:
        return "GitHub · arXiv · Semantic Scholar"
    return "Semantic Scholar · arXiv · CrossRef · GitHub"
