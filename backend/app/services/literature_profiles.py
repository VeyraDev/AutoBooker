"""按书类/体裁决定文献检索数据源组合。"""

from __future__ import annotations

from app.constants.style_types import NONFICTION_STYLES, StyleType

# nonfiction | academic | technical
PROFILE_NONFICTION = "nonfiction"
PROFILE_ACADEMIC = "academic"
PROFILE_TECHNICAL = "technical"

SOURCE_LABELS: dict[str, str] = {
    "wikipedia": "维基百科",
    "crossref": "CrossRef",
    "semantic_scholar": "Semantic Scholar",
    "arxiv": "arXiv",
    "github": "GitHub",
}


def literature_profile(book_type: str, style_type: str | None) -> str:
    st = (style_type or "").strip()
    if st == StyleType.technical_deep_dive.value:
        return PROFILE_TECHNICAL
    if st in {s.value for s in NONFICTION_STYLES}:
        return PROFILE_NONFICTION
    if book_type == "academic":
        return PROFILE_ACADEMIC
    return PROFILE_NONFICTION


def profile_source_hint(profile: str) -> str:
    if profile == PROFILE_NONFICTION:
        return "维基百科 · CrossRef"
    if profile == PROFILE_ACADEMIC:
        return "arXiv · Semantic Scholar · CrossRef"
    if profile == PROFILE_TECHNICAL:
        return "GitHub · arXiv"
    return "CrossRef · Semantic Scholar"
