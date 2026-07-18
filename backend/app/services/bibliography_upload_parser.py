"""Parse user-uploaded bibliography metadata without inventing sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_BIB_MARKERS = ("参考文献", "references", "bibliography")
_ENTRY_START_RE = re.compile(r"^\s*(?:\[(?P<bracket>\d+)\]|(?P<dot>\d+)[.、])\s*(?P<body>.+)")
_DOI_RE = re.compile(r"\b(10\.\d{4,}/[^\s\])>,;，。]+)", re.I)
_URL_RE = re.compile(r"https?://[^\s\])>,;，。]+", re.I)
_ABSTRACT_RE = re.compile(r"^\s*(?:摘要|Abstract)\s*[:：]\s*(?P<value>.+)", re.I)
_KEYWORDS_RE = re.compile(r"^\s*(?:关键词|关键字|Keywords)\s*[:：]\s*(?P<value>.+)", re.I)
_DOI_LINE_RE = re.compile(r"^\s*(?:DOI|doi)\s*[:：]\s*(?P<value>.+)", re.I)
_GB_ENTRY_RE = re.compile(
    r"^(?P<authors>[^.。]+)[.。](?P<title>.+?)\[(?P<doc_type>[A-Za-z])\][.。]?(?P<tail>.*)$"
)
_YEAR_RE = re.compile(r"(19|20)\d{2}")
_VOL_ISSUE_PAGES_RE = re.compile(
    r"(?P<year>(?:19|20)\d{2})\s*[,，]\s*(?P<volume>[^,，:：()（）]+)?"
    r"(?:[(（](?P<issue>[^)）]+)[)）])?\s*[:：]\s*(?P<pages>[\w\-–—,，]+)"
)


@dataclass(frozen=True)
class ParsedBibliographyRecord:
    raw_text: str
    entry_text: str
    title: str
    authors: list[str]
    year: int | None
    journal: str
    doi: str
    url: str
    document_type: str | None
    volume: str | None
    issue: str | None
    pages: str | None
    abstract_preview: str | None
    keywords: list[str]

    def to_paper(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "doi": self.doi,
            "url": self.url,
            "document_type": self.document_type,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "abstract_preview": self.abstract_preview,
            "source": "user_upload",
            "external_id": self.doi or None,
        }


def extract_bibliography_records(text: str, *, limit: int = 80) -> list[ParsedBibliographyRecord]:
    section = _bibliography_section(text)
    grouped = _group_records(section)
    return [parse_bibliography_record(record) for record in grouped[:limit]]


def parse_bibliography_record(raw: str) -> ParsedBibliographyRecord:
    lines = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    entry = ""
    abstract = ""
    keywords: list[str] = []
    extra_lines: list[str] = []
    for line in lines:
        start = _ENTRY_START_RE.match(line)
        if start and not entry:
            entry = start.group("body").strip()
            continue
        if m := _ABSTRACT_RE.match(line):
            abstract = _clean_terminal(m.group("value"))
            continue
        if m := _KEYWORDS_RE.match(line):
            keywords = [p.strip() for p in re.split(r"[;；,，、]", m.group("value")) if p.strip()]
            continue
        extra_lines.append(line)
    if not entry and lines:
        entry = lines[0]
        extra_lines = lines[1:]

    entry_with_extra = "\n".join([entry, *extra_lines]).strip()
    doi = _extract_doi(entry_with_extra)
    url = _extract_url(entry_with_extra)
    parsed = _parse_gb_entry(entry)
    if not parsed["year"]:
        parsed["year"] = _extract_year(entry_with_extra)
    return ParsedBibliographyRecord(
        raw_text=raw.strip(),
        entry_text=entry.strip(),
        title=parsed["title"] or entry[:300],
        authors=parsed["authors"],
        year=parsed["year"],
        journal=parsed["journal"],
        doi=doi,
        url=url,
        document_type=parsed["document_type"],
        volume=parsed["volume"],
        issue=parsed["issue"],
        pages=parsed["pages"],
        abstract_preview=abstract or None,
        keywords=keywords,
    )


def _bibliography_section(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lower = normalized.lower()
    positions = [lower.find(marker.lower()) for marker in _BIB_MARKERS]
    positions = [pos for pos in positions if pos >= 0]
    if not positions:
        return normalized
    section = normalized[min(positions) :]
    return re.sub(r"^[^\n]*\n", "", section, count=1)


def _group_records(section: str) -> list[str]:
    records: list[list[str]] = []
    current: list[str] = []
    for raw in (section or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if _looks_like_next_chapter(line):
            break
        if line.lower() in {"references", "bibliography"} or line == "参考文献":
            continue
        if _ENTRY_START_RE.match(line):
            if current:
                records.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        records.append(current)
    return ["\n".join(record) for record in records if record]


def _parse_gb_entry(entry: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "title": "",
        "authors": [],
        "year": None,
        "journal": "",
        "document_type": None,
        "volume": None,
        "issue": None,
        "pages": None,
    }
    m = _GB_ENTRY_RE.match(entry.strip())
    if not m:
        out["year"] = _extract_year(entry)
        return out
    out["authors"] = _split_authors(m.group("authors"))
    out["title"] = m.group("title").strip()
    out["document_type"] = _document_type(m.group("doc_type"))
    tail = m.group("tail").strip().rstrip(".。")
    parts = [p.strip() for p in re.split(r"[,，]", tail) if p.strip()]
    if parts:
        out["journal"] = parts[0]
    if m2 := _VOL_ISSUE_PAGES_RE.search(tail):
        out["year"] = int(m2.group("year"))
        out["volume"] = _clean_terminal(m2.group("volume") or "") or None
        out["issue"] = _clean_terminal(m2.group("issue") or "") or None
        out["pages"] = _clean_terminal(m2.group("pages") or "") or None
    else:
        out["year"] = _extract_year(tail)
    return out


def _split_authors(raw: str) -> list[str]:
    authors = [p.strip() for p in re.split(r"[,，;；、]", raw or "") if p.strip()]
    return authors[:20]


def _extract_doi(text: str) -> str:
    m = _DOI_RE.search(text or "")
    return m.group(1).rstrip(".,;，。") if m else ""


def _extract_url(text: str) -> str:
    m = _URL_RE.search(text or "")
    return m.group(0).rstrip(".,;，。") if m else ""


def _extract_year(text: str) -> int | None:
    m = _YEAR_RE.search(text or "")
    return int(m.group(0)) if m else None


def _document_type(code: str) -> str | None:
    return {
        "J": "journal_article",
        "M": "book",
        "D": "dissertation",
        "C": "conference_paper",
        "R": "report",
        "N": "newspaper",
        "EB": "web",
    }.get((code or "").upper(), (code or "").upper() or None)


def _clean_terminal(text: str) -> str:
    return (text or "").strip().strip(".。;；,，")


def _looks_like_next_chapter(line: str) -> bool:
    return bool(re.match(r"^第[一二三四五六七八九十\d]+章", line or ""))
