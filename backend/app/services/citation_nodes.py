from __future__ import annotations

import copy
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.models.citation import Citation, CitationEvidence, CitationOccurrence
from app.services.citation_service import in_text_mark, sync_bibliography_chapter

_MARKER = re.compile(
    r"\[\[CITE:(?P<citation>[0-9a-f-]{36})(?:\|(?P<evidence>[0-9a-f-]{36}))?"
    r"(?:\|(?P<mode>parenthetical|narrative|numeric))?(?:\|(?P<locator>[^\]]+))?\]\]",
    re.I,
)
_UNSAFE_CITATION = re.compile(
    r"\((?:[A-Z][A-Za-z' -]+(?:\s+(?:et al\.|&\s*[A-Z][A-Za-z' -]+))?),\s*(?:19|20)\d{2}\)"
    r"|\[(?:\d{1,3})\]"
)
_AUTHOR_YEAR_BEFORE_MARKER = re.compile(
    r"(?:（[^（）\n]{1,100}[，,]\s*(?:19|20)\d{2}[a-z]?）"
    r"|\([^()\n]{1,100},\s*(?:19|20)\d{2}[a-z]?\))\s*$",
    re.I,
)


def _citation_style(book: Book) -> str:
    value = getattr(book, "citation_style", None)
    return str(getattr(value, "value", value) or "apa")


def _citation_display_text(citation: Citation) -> str:
    return f"[{citation.list_index}]" if citation.list_index is not None else "[?]"


def has_internal_citation_markers(doc: dict[str, Any]) -> bool:
    if doc.get("type") == "text" and _MARKER.search(str(doc.get("text") or "")):
        return True
    return any(
        has_internal_citation_markers(child)
        for child in doc.get("content") or []
        if isinstance(child, dict)
    )


def citation_node(
    citation: Citation,
    style: str,
    *,
    evidence_id: uuid.UUID | None = None,
    mode: str = "parenthetical",
    locator: str | None = None,
    prefix: str = "",
    suffix: str = "",
    node_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    return {
        "type": "citation",
        "attrs": {
            "nodeId": str(node_id or uuid.uuid4()),
            "citationId": str(citation.id),
            "evidenceId": str(evidence_id) if evidence_id else "",
            "citeMode": mode,
            "locator": locator or "",
            "prefix": prefix,
            "suffix": suffix,
            "renderedText": render_citation_node(citation, style, mode=mode, locator=locator, prefix=prefix, suffix=suffix),
            "displayText": _citation_display_text(citation),
        },
    }


def render_citation_node(
    citation: Citation,
    style: str,
    *,
    mode: str = "parenthetical",
    locator: str | None = None,
    prefix: str = "",
    suffix: str = "",
) -> str:
    mark = in_text_mark(citation, style)
    if mode == "narrative":
        author = (citation.authors or ["佚名"])[0]
        year = citation.year or "n.d."
        mark = f"{author}（{year}）"
    if locator:
        if mark.endswith(")"):
            mark = f"{mark[:-1]}, {locator})"
        elif mark.endswith("]"):
            mark = f"{mark}（{locator}）"
    return f"{prefix or ''}{mark}{suffix or ''}"


def _plain(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return str(node.get("text") or "")
    if node.get("type") == "citation":
        return str((node.get("attrs") or {}).get("renderedText") or "")
    return "".join(_plain(x) for x in node.get("content") or [])


def _citation_nodes(doc: dict[str, Any]) -> list[tuple[dict[str, Any], str, str]]:
    found: list[tuple[dict[str, Any], str, str]] = []

    def walk(parent: dict[str, Any]) -> None:
        content = parent.get("content") or []
        if not isinstance(content, list):
            return
        for i, node in enumerate(content):
            if not isinstance(node, dict):
                continue
            if node.get("type") == "citation":
                before = "".join(_plain(x) for x in content[:i])[-180:]
                after = "".join(_plain(x) for x in content[i + 1 :])[:180]
                found.append((node, before, after))
            else:
                walk(node)

    walk(doc)
    return found


def sync_chapter_occurrences(db: Session, book: Book, chapter: Chapter) -> None:
    meta = chapter.content if isinstance(chapter.content, dict) else {}
    doc = meta.get("tiptap_json")
    if not isinstance(doc, dict):
        return
    seen: set[uuid.UUID] = set()
    nodes = _citation_nodes(doc)
    if nodes:
        book.structured_citations = True
    for ordinal, (node, before, after) in enumerate(nodes, start=1):
        attrs = node.get("attrs") or {}
        try:
            node_id = uuid.UUID(str(attrs.get("nodeId")))
            citation_id = uuid.UUID(str(attrs.get("citationId")))
        except (TypeError, ValueError):
            continue
        citation = db.query(Citation).filter(Citation.id == citation_id, Citation.book_id == book.id).first()
        if not citation:
            continue
        evidence_id = None
        if attrs.get("evidenceId"):
            try:
                candidate = uuid.UUID(str(attrs["evidenceId"]))
                evidence = db.query(CitationEvidence).filter(
                    CitationEvidence.id == candidate,
                    CitationEvidence.citation_id == citation.id,
                    CitationEvidence.active.is_(True),
                ).first()
                evidence_id = evidence.id if evidence else None
            except (TypeError, ValueError):
                pass
        row = db.query(CitationOccurrence).filter(
            CitationOccurrence.chapter_id == chapter.id,
            CitationOccurrence.node_id == node_id,
        ).first()
        if not row:
            row = CitationOccurrence(
                book_id=book.id, chapter_id=chapter.id, node_id=node_id, citation_id=citation.id
            )
            db.add(row)
        row.citation_id = citation.id
        row.evidence_id = evidence_id
        row.cite_mode = str(attrs.get("citeMode") or "parenthetical")
        row.locator = str(attrs.get("locator") or "") or None
        row.prefix = str(attrs.get("prefix") or "") or None
        row.suffix = str(attrs.get("suffix") or "") or None
        row.ordinal = ordinal
        row.context_before = before
        row.context_after = after
        row.complete = bool(citation.title and (citation.year or citation.doi or citation.url))
        seen.add(node_id)
    stale = db.query(CitationOccurrence).filter(CitationOccurrence.chapter_id == chapter.id)
    if seen:
        stale = stale.filter(~CitationOccurrence.node_id.in_(seen))
    stale.delete(synchronize_session=False)
    db.flush()
    refresh_book_citation_rendering(db, book)
    sync_bibliography_chapter(db, book, commit=False)


def refresh_book_citation_rendering(db: Session, book: Book) -> None:
    style = _citation_style(book)
    occurrences = (
        db.query(CitationOccurrence, Chapter)
        .join(Chapter, CitationOccurrence.chapter_id == Chapter.id)
        .filter(CitationOccurrence.book_id == book.id)
        .order_by(Chapter.index.asc(), CitationOccurrence.ordinal.asc())
        .all()
    )
    ordered_ids: list[uuid.UUID] = []
    for occurrence, _chapter in occurrences:
        if occurrence.citation_id not in ordered_ids:
            ordered_ids.append(occurrence.citation_id)
    citations = db.query(Citation).filter(Citation.book_id == book.id).all()
    by_id = {c.id: c for c in citations}
    for citation in citations:
        citation.list_index = ordered_ids.index(citation.id) + 1 if citation.id in ordered_ids else None
    db.flush()
    for chapter in db.query(Chapter).filter(Chapter.book_id == book.id).all():
        meta = dict(chapter.content) if isinstance(chapter.content, dict) else {}
        doc = meta.get("tiptap_json")
        if not isinstance(doc, dict):
            continue
        changed = False
        for node, _before, _after in _citation_nodes(doc):
            attrs = dict(node.get("attrs") or {})
            try:
                citation = by_id.get(uuid.UUID(str(attrs.get("citationId"))))
            except (TypeError, ValueError):
                citation = None
            if not citation:
                continue
            attrs["renderedText"] = render_citation_node(
                citation, style,
                mode=str(attrs.get("citeMode") or "parenthetical"),
                locator=str(attrs.get("locator") or "") or None,
                prefix=str(attrs.get("prefix") or ""),
                suffix=str(attrs.get("suffix") or ""),
            )
            attrs["displayText"] = _citation_display_text(citation)
            node["attrs"] = attrs
            changed = True
        if changed:
            meta["tiptap_json"] = doc
            chapter.content = meta
    db.flush()


def replace_markers_with_nodes(db: Session, book: Book, doc: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    result = copy.deepcopy(doc)
    unresolved: list[str] = []
    style = _citation_style(book)

    def walk(node: dict[str, Any]) -> None:
        content = node.get("content")
        if not isinstance(content, list):
            return
        output: list[dict[str, Any]] = []
        for child in content:
            if not isinstance(child, dict):
                continue
            if child.get("type") == "text" and _MARKER.search(str(child.get("text") or "")):
                text = str(child.get("text") or "")
                pos = 0
                for match in _MARKER.finditer(text):
                    try:
                        citation_id = uuid.UUID(match.group("citation"))
                    except (TypeError, ValueError):
                        citation_id = None
                    citation = None
                    if citation_id:
                        citation = db.query(Citation).filter(
                            Citation.id == citation_id,
                            Citation.book_id == book.id,
                        ).first()
                    evidence_id = None
                    if match.group("evidence"):
                        try:
                            evidence_id = uuid.UUID(match.group("evidence"))
                        except (TypeError, ValueError):
                            pass
                    leading = text[pos:match.start()]
                    if citation:
                        # 模型有时同时输出“（作者，年份）”与内部标记。结构化节点已经
                        # 负责展示引用，保留前者会造成正文重复，因此只移除紧邻标记的
                        # 作者年份括注，不碰句子中其他括号内容。
                        leading = _AUTHOR_YEAR_BEFORE_MARKER.sub("", leading)
                    if leading:
                        output.append({**child, "text": leading})
                    if citation:
                        output.append(
                            citation_node(
                                citation, style, evidence_id=evidence_id,
                                mode=match.group("mode") or "parenthetical",
                                locator=match.group("locator"),
                            )
                        )
                    else:
                        unresolved.append(match.group(0))
                        output.append({"type": "text", "text": "（待补充来源）"})
                    pos = match.end()
                if pos < len(text):
                    output.append({**child, "text": text[pos:]})
            else:
                walk(child)
                output.append(child)
        node["content"] = output

    walk(result)

    def sanitize(node: dict[str, Any]) -> None:
        if node.get("type") == "text":
            text = str(node.get("text") or "")
            if _UNSAFE_CITATION.search(text):
                unresolved.extend(match.group(0) for match in _UNSAFE_CITATION.finditer(text))
                node["text"] = _UNSAFE_CITATION.sub("（待补充来源）", text)
            return
        for child in node.get("content") or []:
            if isinstance(child, dict):
                sanitize(child)

    sanitize(result)
    return result, unresolved


def normalize_chapter_citations(
    db: Session,
    book: Book,
    chapter: Chapter,
    *,
    doc: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Convert internal markers, persist the TipTap document and resync book-wide order."""
    meta = dict(chapter.content) if isinstance(chapter.content, dict) else {}
    candidate = doc if isinstance(doc, dict) else meta.get("tiptap_json")
    if not isinstance(candidate, dict):
        return None, []
    normalized, unresolved = replace_markers_with_nodes(db, book, candidate)
    meta["tiptap_json"] = normalized
    if unresolved:
        meta["unresolved_citations"] = list(dict.fromkeys(unresolved))
    else:
        meta.pop("unresolved_citations", None)
    chapter.content = meta
    db.flush()
    sync_chapter_occurrences(db, book, chapter)
    refreshed_meta = chapter.content if isinstance(chapter.content, dict) else {}
    refreshed_doc = refreshed_meta.get("tiptap_json")
    return refreshed_doc if isinstance(refreshed_doc, dict) else normalized, unresolved
