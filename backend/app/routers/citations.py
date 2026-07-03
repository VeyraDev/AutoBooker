"""全书引用库：列表、批量添加、插入正文标记、同步参考文献章节。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.literature_agent import lookup_crossref_by_doi
from app.database import get_db
from app.models.book import Book
from app.models.chapter import Chapter
from app.models.citation import Citation, CitationEvidence, CitationOccurrence, CitationSource
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.citation import (
    CitationApplyBibliographyOut,
    CitationBatchIn,
    CitationCreateIn,
    CitationInsertIn,
    CitationInsertOut,
    CitationListOut,
    CitationOut,
    CitationSourceOut,
    CitationWeaveIn,
    CitationWeaveOut,
    CitationNodeIn,
    CitationOccurrenceOut,
    CitationEvidenceOut,
    CitationReplaceIn,
)
from app.services import book_service
from app.services.citation_service import (
    build_bibliography_text,
    create_citation_from_paper,
    formatted_line,
    in_text_mark,
    list_citations_sorted,
    paper_to_dict,
    sync_bibliography_chapter,
)
from app.services.citation_weave import weave_citation_sentence
from app.services.citation_nodes import (
    citation_node,
    has_internal_citation_markers,
    normalize_chapter_citations,
    refresh_book_citation_rendering,
)

router = APIRouter(prefix="/books", tags=["citations"])


def _to_out(c: Citation, book) -> CitationOut:
    style = book.citation_style.value if book.citation_style else "apa"
    return CitationOut.model_validate(c).model_copy(
        update={"formatted": formatted_line(c, style)},
    )


@router.get("/{book_id}/citations", response_model=CitationListOut)
def list_book_citations(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    rows = list_citations_sorted(db, book.id)
    return CitationListOut(items=[_to_out(r, book) for r in rows])


@router.post("/{book_id}/citations", response_model=CitationOut, status_code=status.HTTP_201_CREATED)
def add_citation(
    book_id: UUID,
    body: CitationCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    src = CitationSource(body.source.value)
    row = create_citation_from_paper(
        db,
        book,
        paper_to_dict(body.paper.model_dump()),
        source=src,
        raw_text=body.raw_text,
    )
    return _to_out(row, book)


@router.post("/{book_id}/citations/batch", response_model=CitationListOut)
def add_citations_batch(
    book_id: UUID,
    body: CitationBatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    src = CitationSource(body.source.value)
    created: list[Citation] = []
    for p in body.papers:
        row = create_citation_from_paper(db, book, paper_to_dict(p.model_dump()), source=src)
        created.append(row)
    return CitationListOut(items=[_to_out(r, book) for r in created])


@router.post("/{book_id}/citations/insert", response_model=CitationInsertOut)
def insert_citations(
    book_id: UUID,
    body: CitationInsertIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    style = book.citation_style.value if book.citation_style else "apa"
    rows = (
        db.query(Citation)
        .filter(Citation.book_id == book.id, Citation.id.in_(body.citation_ids))
        .all()
    )
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "未找到所选文献")
    rows = sorted(rows, key=lambda c: c.list_index or 9999)
    marks = [in_text_mark(r, style) for r in rows]
    bib_lines = [formatted_line(r, style) for r in rows]
    if body.sync_bibliography:
        sync_bibliography_chapter(db, book)
    return CitationInsertOut(
        in_text_marks=marks,
        bibliography_lines=bib_lines,
        citations=[_to_out(r, book) for r in rows],
    )


@router.post("/{book_id}/citations/{citation_id}/weave", response_model=CitationWeaveOut)
def weave_citation_for_insert(
    book_id: UUID,
    citation_id: UUID,
    body: CitationWeaveIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """结合光标上下文与文献摘录，生成一句可预览后插入正文的叙述性援引。"""
    book = book_service.get_book_or_404(book_id, user, db)
    row = (
        db.query(Citation)
        .filter(Citation.id == citation_id, Citation.book_id == book.id)
        .first()
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Citation not found")
    sentence = weave_citation_sentence(book=book, citation=row, context=body.context)
    style = book.citation_style.value if book.citation_style else "apa"
    evidence = db.query(CitationEvidence).filter(
        CitationEvidence.citation_id == row.id,
        CitationEvidence.active.is_(True),
    ).order_by(CitationEvidence.created_at).first()
    return CitationWeaveOut(
        sentence=sentence,
        citation_id=row.id,
        node=citation_node(
            row,
            style,
            evidence_id=evidence.id if evidence else None,
            mode="parenthetical",
        ),
    )


@router.post("/{book_id}/citations/{citation_id}/node", response_model=dict)
def create_citation_node(
    book_id: UUID,
    citation_id: UUID,
    body: CitationNodeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    row = db.query(Citation).filter(Citation.id == citation_id, Citation.book_id == book.id).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Citation not found")
    style = book.citation_style.value if book.citation_style else "apa"
    return citation_node(
        row, style, evidence_id=body.evidence_id, mode=body.mode,
        locator=body.locator, prefix=body.prefix, suffix=body.suffix,
    )


@router.get("/{book_id}/citations/{citation_id}/evidence", response_model=list[CitationEvidenceOut])
def list_citation_evidence(
    book_id: UUID,
    citation_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    citation = db.query(Citation).filter(
        Citation.id == citation_id,
        Citation.book_id == book.id,
    ).first()
    if not citation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Citation not found")
    return db.query(CitationEvidence).filter(
        CitationEvidence.citation_id == citation.id,
        CitationEvidence.active.is_(True),
    ).order_by(CitationEvidence.created_at).all()


@router.get("/{book_id}/citation-occurrences", response_model=list[CitationOccurrenceOut])
def list_occurrences(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    repaired = False
    for chapter in db.query(Chapter).filter(Chapter.book_id == book.id).all():
        meta = chapter.content if isinstance(chapter.content, dict) else {}
        doc = meta.get("tiptap_json")
        if isinstance(doc, dict) and has_internal_citation_markers(doc):
            normalize_chapter_citations(db, book, chapter)
            repaired = True
    if repaired:
        db.commit()
    rows = (
        db.query(CitationOccurrence, Chapter, Citation)
        .join(Chapter, CitationOccurrence.chapter_id == Chapter.id)
        .join(Citation, CitationOccurrence.citation_id == Citation.id)
        .filter(CitationOccurrence.book_id == book.id)
        .order_by(Chapter.index, CitationOccurrence.ordinal)
        .all()
    )
    return [
        CitationOccurrenceOut(
            id=o.id, citation_id=o.citation_id, evidence_id=o.evidence_id,
            chapter_id=ch.id, chapter_index=ch.index, chapter_title=ch.title,
            node_id=o.node_id, cite_mode=o.cite_mode, locator=o.locator,
            context_before=o.context_before, context_after=o.context_after,
            complete=o.complete, citation=_to_out(c, book),
        )
        for o, ch, c in rows
    ]


@router.delete("/{book_id}/citation-occurrences/{occurrence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_occurrence(
    book_id: UUID,
    occurrence_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    occurrence = db.query(CitationOccurrence).filter(
        CitationOccurrence.id == occurrence_id,
        CitationOccurrence.book_id == book.id,
    ).first()
    if not occurrence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Occurrence not found")
    chapter = db.get(Chapter, occurrence.chapter_id)
    if chapter and isinstance(chapter.content, dict):
        meta = dict(chapter.content)
        doc = meta.get("tiptap_json")
        if isinstance(doc, dict):
            def remove(nodes):
                out = []
                for node in nodes or []:
                    if isinstance(node, dict):
                        attrs = node.get("attrs") or {}
                        if node.get("type") == "citation" and str(attrs.get("nodeId")) == str(occurrence.node_id):
                            continue
                        if isinstance(node.get("content"), list):
                            node["content"] = remove(node["content"])
                    out.append(node)
                return out
            doc["content"] = remove(doc.get("content"))
            meta["tiptap_json"] = doc
            chapter.content = meta
    db.delete(occurrence)
    db.flush()
    refresh_book_citation_rendering(db, book)
    sync_bibliography_chapter(db, book)
    db.commit()


@router.post("/{book_id}/citation-occurrences/{occurrence_id}/replace", response_model=dict)
def replace_occurrence(
    book_id: UUID,
    occurrence_id: UUID,
    body: CitationReplaceIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    occurrence = db.query(CitationOccurrence).filter(
        CitationOccurrence.id == occurrence_id,
        CitationOccurrence.book_id == book.id,
    ).first()
    citation = db.query(Citation).filter(Citation.id == body.citation_id, Citation.book_id == book.id).first()
    if not occurrence or not citation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Citation occurrence not found")
    evidence = None
    if body.evidence_id:
        evidence = db.query(CitationEvidence).filter(
            CitationEvidence.id == body.evidence_id,
            CitationEvidence.citation_id == citation.id,
            CitationEvidence.active.is_(True),
        ).first()
        if not evidence:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Evidence does not belong to citation")
    occurrence.citation_id = citation.id
    occurrence.evidence_id = evidence.id if evidence else None
    occurrence.complete = bool(citation.title and (citation.year or citation.doi or citation.url))
    chapter = db.get(Chapter, occurrence.chapter_id)
    if chapter and isinstance(chapter.content, dict):
        meta = dict(chapter.content)
        doc = meta.get("tiptap_json")

        def replace(nodes):
            for node in nodes or []:
                if not isinstance(node, dict):
                    continue
                attrs = node.get("attrs") or {}
                if node.get("type") == "citation" and str(attrs.get("nodeId")) == str(occurrence.node_id):
                    node["attrs"] = {
                        **attrs,
                        "citationId": str(citation.id),
                        "evidenceId": str(evidence.id) if evidence else "",
                    }
                replace(node.get("content"))

        if isinstance(doc, dict):
            replace(doc.get("content"))
            meta["tiptap_json"] = doc
            chapter.content = meta
    db.flush()
    refresh_book_citation_rendering(db, book)
    sync_bibliography_chapter(db, book)
    db.commit()
    return {"id": str(occurrence.id), "citation_id": str(citation.id)}


@router.post("/{book_id}/citations/sync-bibliography", response_model=CitationApplyBibliographyOut)
def apply_bibliography(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    text = build_bibliography_text(db, book)
    if not text:
        return CitationApplyBibliographyOut(
            chapter_index=None,
            bibliography_text="",
            message="暂无引用条目",
        )
    ch = sync_bibliography_chapter(db, book)
    return CitationApplyBibliographyOut(
        chapter_index=ch.index if ch else None,
        bibliography_text=text,
        message="已同步书末参考文献章节",
    )


@router.delete("/{book_id}/citations/{citation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_citation(
    book_id: UUID,
    citation_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    row = (
        db.query(Citation)
        .filter(Citation.id == citation_id, Citation.book_id == book.id)
        .first()
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Citation not found")
    if db.query(CitationOccurrence).filter(CitationOccurrence.citation_id == row.id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "请先删除正文中的引用位置")
    db.delete(row)
    db.commit()
    style = book.citation_style.value if book.citation_style else "apa"
    from app.services.citation_service import _reindex_citations

    _reindex_citations(db, book.id, style)
    db.commit()
