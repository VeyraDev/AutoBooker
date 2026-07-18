"""本书文献、引用排序与独立书末参考文献同步。"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.literature_agent import format_paper_citation
from app.services.citation_formats import format_in_text_by_source
from app.services.bibliography_upload_parser import extract_bibliography_records
from app.models.book import Book, CitationStyle
from app.models.chapter import Chapter
from app.models.citation import Citation, CitationEvidence, CitationOccurrence, CitationSource
from app.models.reference import ReferenceChunk

_BIB_CHAPTER_TITLES = ("参考文献", "References", "参考书目", "引用文献")
SEQUENTIAL_CITATION_STYLES = frozenset({"gb_t7714"})

_DOI_RE = re.compile(r"\b(10\.\d{4,}/[^\s\])>,;]+)", re.IGNORECASE)


def _author_sort_key(authors: list[str]) -> str:
    if not authors:
        return "zzz"
    name = (authors[0] or "").strip()
    if not name:
        return "zzz"
    return name.casefold()


def is_sequential_citation_style(style: str | None) -> bool:
    return str(style or "").lower() in SEQUENTIAL_CITATION_STYLES


def bibliography_sort_key(citation: Citation, style: str) -> tuple:
    authors = citation.authors or []
    author = _author_sort_key(authors)
    title = (citation.title or "").casefold()
    year = citation.year if citation.year is not None else 10**9
    if style == "mla":
        return author, title, year
    return author, year, title


def apply_reference_order(
    citations: list[Citation],
    first_occurrence_ids: list[uuid.UUID],
    style: str,
) -> tuple[list[Citation], list[Citation]]:
    """Assign formal numbers only for used sequential-style references."""
    by_id = {row.id: row for row in citations}
    unique_used_ids: list[uuid.UUID] = []
    for citation_id in first_occurrence_ids:
        if citation_id in by_id and citation_id not in unique_used_ids:
            unique_used_ids.append(citation_id)
    used = [by_id[citation_id] for citation_id in unique_used_ids]
    if not is_sequential_citation_style(style):
        used.sort(key=lambda row: bibliography_sort_key(row, style))
    used_ids = set(unique_used_ids)
    unused = sorted(
        [row for row in citations if row.id not in used_ids],
        key=lambda row: bibliography_sort_key(row, style),
    )
    for row in citations:
        row.list_index = None
    if is_sequential_citation_style(style):
        for index, row in enumerate(used, start=1):
            row.list_index = index
    return used, unused


def _first_occurrence_ids(db: Session, book_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        db.query(CitationOccurrence.citation_id)
        .join(Chapter, CitationOccurrence.chapter_id == Chapter.id)
        .filter(CitationOccurrence.book_id == book_id)
        .order_by(Chapter.index.asc(), CitationOccurrence.ordinal.asc())
        .all()
    )
    return [row[0] for row in rows]


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
        "document_type": (paper.get("document_type") or paper.get("type") or "").strip() or None,
        "publisher": (paper.get("publisher") or "").strip() or None,
        "volume": (paper.get("volume") or "").strip() or None,
        "issue": (paper.get("issue") or "").strip() or None,
        "pages": (paper.get("pages") or "").strip() or None,
        "quotable_snippet": (paper.get("quotable_snippet") or "").strip() or None,
    }


def build_format_cache(paper: dict[str, Any], styles: list[str] | None = None) -> dict[str, str]:
    styles = styles or ["apa", "mla", "chicago", "gb_t7714"]
    payload = {**paper, "source": paper.get("source") or ""}
    return {s: format_paper_citation(payload, s) for s in styles}


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
    snippet = data.get("quotable_snippet")

    def ensure_evidence(citation: Citation) -> None:
        quote = snippet or (raw_text or "").strip() or None
        if not quote:
            return
        exists = db.query(CitationEvidence).filter(
            CitationEvidence.citation_id == citation.id,
            CitationEvidence.quote_text == quote,
            CitationEvidence.active.is_(True),
        ).first()
        if not exists:
            source_chunk = None
            if source_file_id:
                candidates = db.query(ReferenceChunk).filter(
                    ReferenceChunk.file_id == source_file_id,
                    ReferenceChunk.active.is_(True),
                ).all()
                needle = re.sub(r"\s+", "", quote)[:60]
                source_chunk = next(
                    (
                        chunk
                        for chunk in candidates
                        if needle and needle in re.sub(r"\s+", "", chunk.content or "")
                    ),
                    None,
                )
            db.add(
                CitationEvidence(
                    citation_id=citation.id,
                    source_file_id=source_file_id,
                    chunk_id=source_chunk.id if source_chunk else None,
                    page_number=source_chunk.page_number if source_chunk else None,
                    paragraph_locator=(
                        str(source_chunk.paragraph_index)
                        if source_chunk and source_chunk.paragraph_index is not None
                        else None
                    ),
                    heading_path=source_chunk.heading_path if source_chunk else None,
                    quote_text=quote,
                    directly_quotable=bool(snippet),
                )
            )

    if doi:
        existing = (
            db.query(Citation)
            .filter(Citation.book_id == book.id, Citation.doi == doi)
            .first()
        )
        if existing:
            if snippet and not existing.quotable_snippet:
                existing.quotable_snippet = snippet
            ab = data.get("abstract_preview")
            if ab and not getattr(existing, "abstract_preview", None):
                existing.abstract_preview = ab
            if data.get("url") and not getattr(existing, "url", None):
                existing.url = data.get("url")
            ensure_evidence(existing)
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
            ab = data.get("abstract_preview")
            if ab and not getattr(existing, "abstract_preview", None):
                existing.abstract_preview = ab
            if data.get("url") and not getattr(existing, "url", None):
                existing.url = data.get("url")
            ensure_evidence(existing)
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
        document_type=data.get("document_type"),
        publisher=data.get("publisher"),
        volume=data.get("volume"),
        issue=data.get("issue"),
        pages=data.get("pages"),
        metadata_status=_citation_metadata_status(data, doi),
        format_cache=cache,
        source=source,
        source_file_id=source_file_id,
        raw_text=raw_text,
        external_source=ext_src,
        external_id=ext_id,
        quotable_snippet=snippet,
        abstract_preview=data.get("abstract_preview"),
        url=data.get("url"),
    )
    db.add(row)
    db.flush()
    ensure_evidence(row)
    _reindex_citations(db, book.id, style)
    db.commit()
    db.refresh(row)
    return row


def _citation_metadata_status(data: dict[str, Any], doi: str | None) -> str:
    has_core = bool(data["title"] and data["authors"] and (data["year"] or doi or data.get("url")))
    if not has_core:
        return "needs_completion"
    doc_type = str(data.get("document_type") or "").lower()
    is_uploaded = str(data.get("source") or "").lower() == "user_upload"
    academic_type = doc_type in {"journal_article", "dissertation", "conference_paper", "j", "d", "c"}
    if is_uploaded and academic_type and not data.get("abstract_preview"):
        return "needs_completion"
    return "complete"


def list_citations_sorted(db: Session, book_id: uuid.UUID) -> list[Citation]:
    rows = db.query(Citation).filter(Citation.book_id == book_id).all()
    rows.sort(key=lambda c: (_author_sort_key(c.authors or []), c.year or 0, c.title or ""))
    return rows


def list_citations_for_management(db: Session, book: Book) -> list[Citation]:
    style = book.citation_style.value if book.citation_style else "apa"
    rows = db.query(Citation).filter(Citation.book_id == book.id).all()
    used, unused = apply_reference_order(rows, _first_occurrence_ids(db, book.id), style)
    db.flush()
    return [*used, *unused]


def _reindex_citations(db: Session, book_id: uuid.UUID, style: str) -> None:
    rows = db.query(Citation).filter(Citation.book_id == book_id).all()
    apply_reference_order(rows, _first_occurrence_ids(db, book_id), style)
    for row in rows:
        paper = {
            "title": row.title,
            "year": row.year,
            "authors": row.authors or [],
            "journal": row.journal or "",
            "doi": row.doi or "",
            "source": row.external_source or "",
            "external_id": row.external_id or "",
            "url": getattr(row, "url", None),
        }
        cache = dict(row.format_cache or {})
        cache[style] = format_paper_citation(
            paper,
            style,
            index=row.list_index if is_sequential_citation_style(style) else None,
        )
        row.format_cache = cache


def formatted_line(citation: Citation, style: str) -> str:
    cache = citation.format_cache or {}
    if style in cache and style != "gb_t7714":
        return cache[style]
    paper = {
        "title": citation.title,
        "year": citation.year,
        "authors": citation.authors or [],
        "journal": citation.journal or "",
        "doi": citation.doi or "",
        "source": citation.external_source or "",
        "external_id": citation.external_id or "",
        "url": getattr(citation, "url", None),
        "document_type": citation.document_type,
        "publisher": citation.publisher,
        "volume": citation.volume,
        "issue": citation.issue,
        "pages": citation.pages,
    }
    idx = citation.list_index if style == "gb_t7714" else None
    return format_paper_citation(paper, style, index=idx)


def in_text_mark(citation: Citation, style: str) -> str:
    ext = (citation.external_source or "").lower()
    if ext in ("github", "wikipedia", "official_doc"):
        return format_in_text_by_source(
            {
                "source": ext,
                "title": citation.title,
                "authors": citation.authors or [],
                "year": citation.year,
                "external_id": citation.external_id,
                "url": getattr(citation, "url", None),
            },
            style,
            list_index=citation.list_index,
        )
    authors = citation.authors or []
    year = citation.year or "n.d."
    if style == "gb_t7714":
        return f"[{citation.list_index}]" if citation.list_index is not None else "[待编号]"
    first = authors[0].split()[-1] if authors else "Anonymous"
    if style == "mla":
        if len(authors) == 2:
            second = authors[1].split()[-1]
            return f"({first} and {second})"
        return f"({first}{' et al.' if len(authors) > 2 else ''})"
    if style == "chicago":
        if len(authors) == 2:
            second = authors[1].split()[-1]
            return f"({first} and {second} {year})"
        return f"({first}{' et al.' if len(authors) > 2 else ''} {year})"
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
        title = (ch.title or "").strip().casefold()
        if title in {item.casefold() for item in _BIB_CHAPTER_TITLES}:
            return ch
    return None


def is_bibliography_chapter(chapter: Chapter) -> bool:
    title = (chapter.title or "").strip().casefold()
    return title in {item.casefold() for item in _BIB_CHAPTER_TITLES}


def build_bibliography_text(db: Session, book: Book) -> str:
    style = book.citation_style.value if book.citation_style else "apa"
    rows = db.query(Citation).filter(Citation.book_id == book.id).all()
    rows, _unused = apply_reference_order(rows, _first_occurrence_ids(db, book.id), style)
    if not rows:
        return ""
    lines = [formatted_line(r, style) for r in rows]
    return "\n\n".join(lines)


def sync_book_bibliography(
    db: Session,
    book: Book,
    *,
    commit: bool = True,
) -> dict[str, Any] | None:
    text = build_bibliography_text(db, book)
    legacy_chapters = [
        chapter
        for chapter in db.query(Chapter).filter(Chapter.book_id == book.id).all()
        if is_bibliography_chapter(chapter)
    ]
    for chapter in legacy_chapters:
        db.delete(chapter)
    if not text:
        book.bibliography = None
        db.commit() if commit else db.flush()
        return None
    payload = {
        "title": "参考文献",
        "text": text,
        "tiptap_json": {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": line}]}
                for line in text.split("\n\n")
            ],
        },
    }
    book.bibliography = payload
    db.commit() if commit else db.flush()
    if commit:
        db.refresh(book)
    return payload


def sync_bibliography_chapter(
    db: Session,
    book: Book,
    *,
    commit: bool = True,
) -> dict[str, Any] | None:
    """Compatibility alias; bibliography is no longer stored as a Chapter."""
    return sync_book_bibliography(db, book, commit=commit)


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
    records = extract_bibliography_records(text)
    added = 0
    for record in records:
        line = record.entry_text or record.raw_text
        doi = record.doi or parse_doi_from_line(line)
        paper: dict[str, Any] | None = None
        if doi and lookup_doi:
            paper = _merge_uploaded_paper_metadata(record.to_paper(), lookup_doi(doi))
        if not paper:
            paper = record.to_paper()
        before = db.query(Citation).filter(Citation.book_id == book.id).count()
        create_citation_from_paper(
            db,
            book,
            paper,
            source=CitationSource.uploaded_file,
            source_file_id=file_id,
            raw_text=record.raw_text or line,
        )
        after = db.query(Citation).filter(Citation.book_id == book.id).count()
        if after > before:
            added += 1
    return added


def _merge_uploaded_paper_metadata(uploaded: dict[str, Any], looked_up: dict[str, Any] | None) -> dict[str, Any]:
    if not looked_up:
        return uploaded
    merged = dict(uploaded)
    for key, value in looked_up.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    for key in ("abstract_preview", "volume", "issue", "pages", "url", "document_type"):
        if not merged.get(key) and uploaded.get(key):
            merged[key] = uploaded[key]
    if not merged.get("source"):
        merged["source"] = uploaded.get("source") or "user_upload"
    return merged
