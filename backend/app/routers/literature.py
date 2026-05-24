"""文献搜索（多源）与引用段落插入。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.literature_agent import LiteratureAgent, format_paper_citation
from app.database import get_db
from app.models.citation import CitationSource
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.citation import CitationBatchIn, CitationListOut, CitationOut
from app.schemas.literature import (
    LiteratureFormatIn,
    LiteratureFormatOut,
    LiteratureInsertQuotesOut,
    LiteraturePaperOut,
    LiteratureQuoteBlockOut,
    LiteratureSearchIn,
    LiteratureSearchOut,
)
from app.services import book_service
from app.services.citation_service import (
    create_citation_from_paper,
    formatted_line,
    in_text_mark,
    paper_to_dict,
    sync_bibliography_chapter,
)
from app.services.literature_content import build_quote_paragraph, fetch_paper_quotable_snippet
from app.services.literature_profiles import (
    SOURCE_LABELS,
    literature_profile,
    profile_source_hint,
)

router = APIRouter(prefix="/books", tags=["literature"])


def _paper_payload(p) -> dict:
    d = p.model_dump() if hasattr(p, "model_dump") else dict(p)
    return {k: v for k, v in d.items() if v is not None}


@router.post("/{book_id}/literature/search", response_model=LiteratureSearchOut)
def literature_search(
    book_id: UUID,
    body: LiteratureSearchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    profile = literature_profile(book.book_type, book.style_type)
    agent = LiteratureAgent()
    raw = agent.search_by_profile(body.query, profile, rows=body.rows)
    items = [LiteraturePaperOut.model_validate(x) for x in raw]
    return LiteratureSearchOut(
        items=items,
        profile=profile,
        source_hint=profile_source_hint(profile),
    )


@router.post("/{book_id}/literature/format", response_model=LiteratureFormatOut)
def literature_format(
    book_id: UUID,
    body: LiteratureFormatIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    text = format_paper_citation(body.paper, body.style, index=body.index)
    return LiteratureFormatOut(citation=text)


@router.post("/{book_id}/literature/add-selected", response_model=CitationListOut)
def literature_add_selected(
    book_id: UUID,
    body: CitationBatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将用户勾选的检索结果写入引用库（不插入正文）。"""
    book = book_service.get_book_or_404(book_id, user, db)
    style = book.citation_style.value if book.citation_style else "apa"
    created: list = []
    for p in body.papers:
        payload = _paper_payload(p)
        snippet, _ = fetch_paper_quotable_snippet(payload)
        if snippet:
            payload["quotable_snippet"] = snippet
        row = create_citation_from_paper(
            db,
            book,
            payload,
            source=CitationSource.literature_search,
        )
        created.append(row)
    return CitationListOut(
        items=[
            CitationOut.model_validate(r).model_copy(update={"formatted": formatted_line(r, style)})
            for r in created
        ],
    )


@router.post("/{book_id}/literature/insert-selected", response_model=LiteratureInsertQuotesOut)
def literature_insert_selected(
    book_id: UUID,
    body: CitationBatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    勾选文献 → 抓取可引用片段 → 写入引用库 → 返回可插入正文的引用段落。
    """
    book = book_service.get_book_or_404(book_id, user, db)
    style = book.citation_style.value if book.citation_style else "apa"
    quote_blocks: list[LiteratureQuoteBlockOut] = []
    citation_rows: list = []

    for p in body.papers:
        payload = _paper_payload(p)
        snippet, fetch_status = fetch_paper_quotable_snippet(payload)
        if snippet:
            payload["quotable_snippet"] = snippet
        row = create_citation_from_paper(
            db,
            book,
            {**payload, **paper_to_dict(payload)},
            source=CitationSource.literature_search,
        )
        if snippet and not row.quotable_snippet:
            row.quotable_snippet = snippet
            db.commit()
            db.refresh(row)
        use_snippet = (row.quotable_snippet or snippet or "").strip()
        mark = in_text_mark(row, style)
        src = (payload.get("source") or row.external_source or "").lower()
        label = SOURCE_LABELS.get(src, "") or payload.get("source_label") or src
        quote_body = build_quote_paragraph(
            in_text_mark=mark,
            snippet=use_snippet,
            source_label=label,
            title=row.title,
        )
        quote_blocks.append(
            LiteratureQuoteBlockOut(
                citation_id=str(row.id),
                in_text_mark=mark,
                quote_body=quote_body,
                bibliography_line=formatted_line(row, style),
                fetch_status=fetch_status,
                source_label=label,
                title=row.title,
            )
        )
        citation_rows.append(row)

    sync_bibliography_chapter(db, book)
    return LiteratureInsertQuotesOut(
        quotes=quote_blocks,
        citations=[
            CitationOut.model_validate(r).model_copy(update={"formatted": formatted_line(r, style)})
            for r in citation_rows
        ],
    )
