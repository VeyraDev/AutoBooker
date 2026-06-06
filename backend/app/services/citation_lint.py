"""程序化扫描正文引用与无来源断言。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.citation import Citation
from app.services.review_anchor import locate_issue_anchor
from app.services.review_scoring import SEVERITY_DEFAULT_PENALTY, standardize_issue

_UNSUPPORTED_PATTERNS = [
    (re.compile(r"研究表明"), "unsupported_assertion"),
    (re.compile(r"有数据显示"), "unsupported_assertion"),
    (re.compile(r"据报道"), "unsupported_assertion"),
    (re.compile(r"专家指出"), "unsupported_assertion"),
    (re.compile(r"调查显示"), "unsupported_assertion"),
]

_PAREN_CITE = re.compile(
    r"\(([A-Za-z\u4e00-\u9fff][^,()]{0,40}?)\s*,\s*(\d{4}|n\.d\.)\)",
)
_BRACKET_CITE = re.compile(r"\[(\d{1,3})\]")
_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_SPECIFIC_CLAIM_RE = re.compile(
    r"[^。！？\n]{0,80}(?:\d{4}年|\d+(?:\.\d+)?%|\d+(?:\.\d+)?(?:万|亿|人|家|次|元|美元|小时|分钟)|研究表明|调查显示|数据显示|案例显示)[^。！？\n]{0,80}"
)


@dataclass
class CitationLintIssue:
    kind: str
    quote: str
    detail: str
    suggested_title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "quote": self.quote,
            "detail": self.detail,
            "suggested_title": self.suggested_title,
        }


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").casefold())


def _match_citation(
    author_hint: str,
    year: str,
    rows: list[Citation],
) -> Citation | None:
    ah = _norm(author_hint)
    for c in rows:
        authors = c.authors or []
        for a in authors:
            if ah and ah in _norm(a):
                y = str(c.year or "n.d.")
                if year == "n.d." or str(c.year) == year:
                    return c
        if ah and ah in _norm(c.title or ""):
            return c
    return None


def _match_bracket(index: int, rows: list[Citation]) -> bool:
    for c in rows:
        if c.list_index == index:
            return True
    return False


def _strip_code_regions(text: str) -> str:
    s = _FENCE_RE.sub(" ", text)
    return _INLINE_CODE_RE.sub(" ", s)


def lint_chapter_citations(
    body: str,
    db: Session,
    book_id: uuid.UUID,
    *,
    bracket_style: bool = True,
) -> list[CitationLintIssue]:
    text = _strip_code_regions((body or "").strip())
    if not text:
        return []

    rows = db.query(Citation).filter(Citation.book_id == book_id).all()
    issues: list[CitationLintIssue] = []
    seen: set[str] = set()

    for pat, kind in _UNSUPPORTED_PATTERNS:
        for m in pat.finditer(text):
            key = f"{kind}:{m.start()}"
            if key in seen:
                continue
            seen.add(key)
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            issues.append(
                CitationLintIssue(
                    kind=kind,
                    quote=text[start:end],
                    detail="检测到无具体来源的笼统断言，请补充引用标注或改写为原理性表述。",
                )
            )

    for m in _SPECIFIC_CLAIM_RE.finditer(text):
        if len(issues) >= 24:
            break
        if _has_nearby_citation(text, m.start(), m.end()):
            continue
        quote = m.group(0).strip()
        if len(quote) < 12:
            continue
        key = f"specific:{m.start()}"
        if key in seen:
            continue
        seen.add(key)
        issues.append(
            CitationLintIssue(
                kind="unsupported_assertion",
                quote=quote[:220],
                detail="检测到具体数据、年份、案例或研究结论，但邻近文本未发现引用标注，请补充来源或改写为非断言表达。",
            )
        )

    for m in _PAREN_CITE.finditer(text):
        author, year = m.group(1), m.group(2)
        if not _match_citation(author, year, rows):
            key = f"cite:{m.group(0)}"
            if key in seen:
                continue
            seen.add(key)
            issues.append(
                CitationLintIssue(
                    kind="not_in_library",
                    quote=m.group(0),
                    detail=f"正文引用「{m.group(0)}」未在本书引用库中找到，请入库或删除。",
                    suggested_title=author,
                )
            )

    for m in _BRACKET_CITE.finditer(text):
        if not bracket_style:
            continue
        idx = int(m.group(1))
        if idx < 1:
            continue
        if rows and not _match_bracket(idx, rows):
            key = f"br:{idx}"
            if key in seen:
                continue
            seen.add(key)
            issues.append(
                CitationLintIssue(
                    kind="not_in_library",
                    quote=m.group(0),
                    detail=f"序号引用 [{idx}] 不在当前引用库编号范围内。",
                )
            )

    return issues[:30]


def _has_nearby_citation(text: str, start: int, end: int, *, window: int = 120) -> bool:
    region = text[max(0, start - window) : min(len(text), end + window)]
    return bool(_PAREN_CITE.search(region) or _BRACKET_CITE.search(region))


_KIND_TO_ISSUE_TYPE = {
    "unsupported_assertion": "missing_citation",
    "not_in_library": "broken_reference",
    "invalid_citation_format": "invalid_citation_format",
    "unused_reference": "unused_reference",
    "duplicate_reference": "duplicate_reference",
    "missing_bibliography_item": "missing_bibliography_item",
}


def lint_chapter_citation_detector(
    body: str,
    db: Session,
    book_id: uuid.UUID,
    *,
    bracket_style: bool = True,
) -> dict[str, Any]:
    """返回新版审校聚合器使用的统一 detector result。"""
    raw = lint_chapter_citations(body, db, book_id, bracket_style=bracket_style)
    issues: list[dict[str, Any]] = []
    for item in raw:
        severity = "medium" if item.kind == "unsupported_assertion" else "high"
        loc = locate_issue_anchor(body, quote=item.quote)
        issues.append(
            standardize_issue(
                {
                    "dimension": "citation_sources",
                    "issue_type": _KIND_TO_ISSUE_TYPE.get(item.kind, item.kind),
                    "severity": severity,
                    "penalty": SEVERITY_DEFAULT_PENALTY[severity],
                    "title": _citation_title(item.kind),
                    "explanation": item.detail,
                    "quote": item.quote,
                    "action": "revise",
                    "replacement_text": "",
                    "paragraph_index": loc.paragraph_index,
                    "char_start": loc.char_start,
                    "char_end": loc.char_end,
                    "anchor_hash": loc.anchor_hash,
                    "quality_evidence": {
                        "kind": item.kind,
                        "suggested_title": item.suggested_title,
                        "nearby_citation_required": item.kind == "unsupported_assertion",
                    },
                    "detector": "citation_lint",
                    "confidence": 0.88,
                },
                detector="citation_lint",
            )
        )
    return {
        "dimension": "citation_sources",
        "raw_score": 100,
        "summary": "引用来源检测完成。" if issues else "引用格式、来源库匹配和无来源断言未发现明显问题。",
        "detector": "citation_lint",
        "confidence": 0.9,
        "status": "completed",
        "issues": issues,
    }


def _citation_title(kind: str) -> str:
    return {
        "unsupported_assertion": "断言缺少来源",
        "not_in_library": "引用未入库",
        "invalid_citation_format": "引用格式异常",
        "unused_reference": "参考文献未使用",
        "duplicate_reference": "重复引用",
        "missing_bibliography_item": "参考文献缺失",
    }.get(kind, "引用来源问题")
