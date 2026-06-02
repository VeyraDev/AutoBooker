"""审校维度加权评分。"""

from __future__ import annotations

from typing import Any

DIMENSION_WEIGHTS: dict[str, float] = {
    "logic": 0.15,
    "grammar": 0.15,
    "style": 0.10,
    "citation": 0.20,
    "hallucination": 0.15,
    "figure": 0.15,
    "ai_feature": 0.10,
}

CATEGORY_TO_DIMENSION: dict[str, str] = {
    "logic": "logic",
    "structure": "logic",
    "grammar": "grammar",
    "style": "style",
    "consistency": "style",
    "citation": "citation",
    "hallucination": "hallucination",
    "figure": "figure",
    "code": "logic",
    "other": "grammar",
}


def compute_overall_score(dimensions: dict[str, int]) -> int:
    total = 0.0
    for key, weight in DIMENSION_WEIGHTS.items():
        score = dimensions.get(key, 70)
        try:
            score = max(0, min(100, int(score)))
        except (TypeError, ValueError):
            score = 70
        total += score * weight
    return int(round(total))


def normalize_dimensions(raw: dict[str, Any] | None) -> dict[str, int]:
    dims: dict[str, int] = {}
    if not raw:
        raw = {}
    for key in DIMENSION_WEIGHTS:
        val = raw.get(key, 70)
        try:
            dims[key] = max(0, min(100, int(val)))
        except (TypeError, ValueError):
            dims[key] = 70
    return dims


def attach_paragraph_indices(md: str, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paragraphs: list[tuple[int, str]] = []
    pos = 0
    for block in md.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        start = md.find(block, pos)
        if start < 0:
            start = pos
        paragraphs.append((start, block))
        pos = start + len(block)

    out: list[dict[str, Any]] = []
    for item in issues:
        issue = dict(item)
        quote = (issue.get("quote") or "").strip()
        issue["paragraph_index"] = None
        issue["char_offset"] = None
        if quote:
            idx = md.find(quote)
            if idx >= 0:
                issue["char_offset"] = idx
            for pi, (pstart, para) in enumerate(paragraphs):
                if quote in para or (len(quote) > 12 and quote[:40] in para):
                    issue["paragraph_index"] = pi
                    if issue["char_offset"] is None:
                        issue["char_offset"] = pstart
                    break
        issue["dimension"] = CATEGORY_TO_DIMENSION.get(
            str(issue.get("category") or "other"), "grammar"
        )
        out.append(issue)
    return out
