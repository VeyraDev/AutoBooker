"""程序化扫描正文引用与无来源断言。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.citation import Citation

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
