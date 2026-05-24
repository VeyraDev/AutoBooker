"""引用库 CRUD、排序与书末参考文献章节同步。"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.literature_agent import format_paper_citation
from app.models.book import Book, CitationStyle
from app.models.chapter import Chapter
from app.models.citation import Citation, CitationSource

_BIB_CHAPTER_TITLES = ("参考文献", "References", "参考书目", "引用文献")

_DOI_RE = re.compile(r"\b(10\.\d{4,}/[^\s\])>,;]+)", re.IGNORECASE)


def _author_sort_key(authors: list[str]) -> str:
    if not authors:
        return "zzz"
    name = (authors[0] or "").strip()
    if not name:
        return "zzz"
    return name.casefold()


def paper_to_dict(paper: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": (paper.get("title") or "").strip(),
        "year": paper.get("year"),
        "authors": list(paper.get("authors") or []),
        "journal": (paper.get("journal") or "").strip(),
        "doi": (paper.get("doi") or "").strip(),
        "source": (paper.get("source") or "").strip() or None,
        "source_label": (paper.get("source_label") or "").strip() or None,
        "external_id": (paper.get("external_id") or "").strip() or None,
        "semantic_scholar_id": (paper.get("semantic_scholar_id") or "").strip() or None,
        "abstract_preview": (paper.get("abstract_preview") or "").strip() or None,
        "url": (paper.get("url") or "").strip() or None,
    }


def build_format_cache(paper: dict[str, Any], styles: list[str] | None = None) -> dict[str, str]:
    styles = styles or ["apa", "mla", "chicago", "gb_t7714"]
    return {s: format_paper_citation(paper, s) for s in styles}


def create_citation_from_paper(
    db: Session,
    book: Book,
    paper: dict[str, Any],
    *,
    source: CitationSource = CitationSource.literature_search,
    source_file_id: uuid.UUID | None = None,
    raw_text: str | None = None,
) -> Citation:
    data = paper_to_dict(paper)
    doi = data["doi"] or None
    ext_src = data.get("source")
    ext_id = data.get("external_id")
    snippet = (paper.get("quotable_snippet") or "").strip() or None

    if doi:
        existing = (
            db.query(Citation)
            .filter(Citation.book_id == book.id, Citation.doi == doi)
            .first()
        )
        if existing:
            if snippet and not existing.quotable_snippet:
                existing.quotable_snippet = snippet
                db.commit()
                db.refresh(existing)
            return existing
    if ext_src and ext_id:
        existing = (
            db.query(Citation)
            .filter(
                Citation.book_id == book.id,
                Citation.external_source == ext_src,
                Citation.external_id == ext_id,
            )
            .first()
        )
        if existing:
            if snippet and not existing.quotable_snippet:
                existing.quotable_snippet = snippet
                db.commit()
                db.refresh(existing)
            return existing

    style = book.citation_style.value if book.citation_style else "apa"
    cache = build_format_cache(data)
    row = Citation(
        book_id=book.id,
        doi=doi,
        title=data["title"] or (raw_text or "未命名文献")[:500],
        authors=data["authors"],
        year=data["year"],
        journal=data["journal"] or None,
        format_cache=cache,
        source=source,
        source_file_id=source_file_id,
        raw_text=raw_text,
        external_source=ext_src,
        external_id=ext_id,
        quotable_snippet=snippet,
    )
    db.add(row)
    db.flush()
    _reindex_citations(db, book.id, style)
    db.commit()
    db.refresh(row)
    return row


def list_citations_sorted(db: Session, book_id: uuid.UUID) -> list[Citation]:
    rows = db.query(Citation).filter(Citation.book_id == book_id).all()
    rows.sort(key=lambda c: (_author_sort_key(c.authors or []), c.year or 0, c.title or ""))
    return rows


def _reindex_citations(db: Session, book_id: uuid.UUID, style: str) -> None:
    rows = list_citations_sorted(db, book_id)
    for i, row in enumerate(rows, start=1):
        row.list_index = i
        paper = {
            "title": row.title,
            "year": row.year,
            "authors": row.authors or [],
            "journal": row.journal or "",
            "doi": row.doi or "",
        }
        cache = dict(row.format_cache or {})
        cache[style] = format_paper_citation(paper, style, index=i if style == "gb_t7714" else None)
        row.format_cache = cache


def formatted_line(citation: Citation, style: str) -> str:
    cache = citation.format_cache or {}
    if style in cache:
        return cache[style]
    paper = {
        "title": citation.title,
        "year": citation.year,
        "authors": citation.authors or [],
        "journal": citation.journal or "",
        "doi": citation.doi or "",
    }
    idx = citation.list_index if style == "gb_t7714" else None
    return format_paper_citation(paper, style, index=idx)


def in_text_mark(citation: Citation, style: str) -> str:
    authors = citation.authors or []
    year = citation.year or "n.d."
    if style == "gb_t7714":
        n = citation.list_index or 1
        return f"[{n}]"
    first = authors[0].split()[-1] if authors else "Anonymous"
    if len(authors) > 2:
        return f"({first} et al., {year})"
    if len(authors) == 2:
        second = authors[1].split()[-1]
        return f"({first} & {second}, {year})"
    return f"({first}, {year})"


def find_bibliography_chapter(db: Session, book_id: uuid.UUID) -> Chapter | None:
    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id)
        .order_by(Chapter.index)
        .all()
    )
    for ch in chapters:
        title = (ch.title or "").strip()
        if any(k in title for k in _BIB_CHAPTER_TITLES):
            return ch
    return None


def build_bibliography_text(db: Session, book: Book) -> str:
    style = book.citation_style.value if book.citation_style else "apa"
    rows = list_citations_sorted(db, book.id)
    if not rows:
        return ""
    lines = [formatted_line(r, style) for r in rows]
    return "\n\n".join(lines)


def sync_bibliography_chapter(db: Session, book: Book) -> Chapter | None:
    text = build_bibliography_text(db, book)
    if not text:
        return None
    ch = find_bibliography_chapter(db, book.id)
    if not ch:
        max_idx = (
            db.query(Chapter.index)
            .filter(Chapter.book_id == book.id)
            .order_by(Chapter.index.desc())
            .first()
        )
        next_idx = (max_idx[0] if max_idx else 0) + 1
        ch = Chapter(
            book_id=book.id,
            index=next_idx,
            title="参考文献",
            summary="全书引用文献列表（自动维护）",
            content={
                "text": text,
                "tiptap_json": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "heading",
                            "attrs": {"level": 1},
                            "content": [{"type": "text", "text": "参考文献"}],
                        },
                        *[
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": ln}],
                            }
                            for ln in text.split("\n\n")
                        ],
                    ],
                },
            },
            word_count=len(text),
        )
        db.add(ch)
    else:
        ch.content = {
            "text": text,
            "tiptap_json": {
                "type": "doc",
                "content": [
                    {
                        "type": "heading",
                        "attrs": {"level": 1},
                        "content": [{"type": "text", "text": ch.title or "参考文献"}],
                    },
                    *[
                        {"type": "paragraph", "content": [{"type": "text", "text": ln}]}
                        for ln in text.split("\n\n")
                    ],
                ],
            },
        }
        ch.word_count = len(text)
    db.commit()
    db.refresh(ch)
    return ch


def extract_bibliography_lines(text: str) -> list[str]:
    """从全文中截取参考文献条目行。"""
    lower = text.lower()
    start = -1
    for marker in ("参考文献", "references", "bibliography"):
        pos = lower.find(marker.lower())
        if pos >= 0:
            start = pos
            break
    if start < 0:
        return []
    section = text[start:]
    section = re.sub(r"^[^\n]*\n", "", section, count=1)
    lines: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line or len(line) < 12:
            continue
        if re.match(r"^第[一二三四五六七八九十\d]+章", line):
            break
        if line.lower() in ("references", "bibliography", "参考文献"):
            continue
        lines.append(line)
    return lines[:80]


def parse_doi_from_line(line: str) -> str | None:
    m = _DOI_RE.search(line)
    return m.group(1).rstrip(".,;") if m else None


def ingest_uploaded_bibliography(
    db: Session,
    book: Book,
    text: str,
    file_id: uuid.UUID,
    *,
    lookup_doi,
) -> int:
    """从上传文献的参考文献节解析条目并入库。返回新增条数。"""
    lines = extract_bibliography_lines(text)
    added = 0
    for line in lines:
        doi = parse_doi_from_line(line)
        paper: dict[str, Any] | None = None
        if doi and lookup_doi:
            paper = lookup_doi(doi)
        if not paper:
            paper = {
                "title": line[:300],
                "authors": [],
                "year": None,
                "journal": "",
                "doi": doi or "",
            }
        before = db.query(Citation).filter(Citation.book_id == book.id).count()
        create_citation_from_paper(
            db,
            book,
            paper,
            source=CitationSource.uploaded_file,
            source_file_id=file_id,
            raw_text=line,
        )
        after = db.query(Citation).filter(Citation.book_id == book.id).count()
        if after > before:
            added += 1
    return added
