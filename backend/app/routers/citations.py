"""全书引用库：列表、批量添加、插入正文标记、同步参考文献章节。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.literature_agent import lookup_crossref_by_doi
from app.database import get_db
from app.models.book import Book
from app.models.citation import Citation, CitationSource
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
    return CitationWeaveOut(sentence=sentence, citation_id=row.id)


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
    db.delete(row)
    db.commit()
    style = book.citation_style.value if book.citation_style else "apa"
    from app.services.citation_service import _reindex_citations

    _reindex_citations(db, book.id, style)
    db.commit()
