"""文献搜索（多源）与引用段落插入。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.literature_agent import format_paper_citation
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
    LiteratureRefineQueryIn,
    LiteratureRefineQueryOut,
    LiteratureSearchIn,
    LiteratureSearchOut,
)
from app.schemas.source_search import SourceSearchIn
from app.services import book_service
from app.services.citation_service import (
    create_citation_from_paper,
    formatted_line,
    in_text_mark,
    paper_to_dict,
)
from app.services.literature_content import build_quote_paragraph, fetch_paper_quotable_snippet
from app.services.literature_profiles import SOURCE_LABELS
from app.services.literature_query_refiner import refine_literature_query
from app.services.source_search.service import UnifiedSourceSearchService

router = APIRouter(prefix="/books", tags=["literature"])


def _paper_payload(p) -> dict:
    d = p.model_dump() if hasattr(p, "model_dump") else dict(p)
    return {k: v for k, v in d.items() if v is not None}


def _to_papers(raw: list) -> list[LiteraturePaperOut]:
    return [LiteraturePaperOut.model_validate(x) for x in raw]


@router.post("/{book_id}/literature/refine-query", response_model=LiteratureRefineQueryOut)
def literature_refine_query(
    book_id: UUID,
    body: LiteratureRefineQueryIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    data = refine_literature_query(
        db,
        book,
        raw_query=body.raw_query,
        scope=body.scope,
        chapter_index=body.chapter_index,
    )
    book.last_literature_query = {
        "query": body.raw_query,
        "refined_queries": data["refined_queries"],
        "must_include": data["must_include"],
        "must_exclude": data["must_exclude"],
    }
    db.commit()
    return LiteratureRefineQueryOut.model_validate(data)


@router.post("/{book_id}/literature/search", response_model=LiteratureSearchOut)
def literature_search(
    book_id: UUID,
    body: LiteratureSearchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    raw_q = body.query.strip() or next((q.strip() for q in (body.refined_queries or []) if q.strip()), "")

    if not raw_q:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请提供检索词或先生成检索词")
    unified = UnifiedSourceSearchService().search(
        SourceSearchIn(
            query=raw_q,
            rows=body.rows,
            requested_source_types=["paper", "technical", "web"],
        ),
        book=book,
    )
    papers = _to_papers(unified.papers)
    github = _to_papers(unified.github)
    wiki = _to_papers(unified.wiki)
    official = _to_papers(unified.official_docs)
    flat = papers + github + wiki + official

    book.last_literature_query = {
        "query": raw_q,
        "refined_queries": unified.refined_queries,
        "intent": unified.plan.intent.model_dump(),
        "execution": unified.execution.model_dump(),
    }
    db.commit()

    return LiteratureSearchOut(
        papers=papers,
        github=github,
        wiki=wiki,
        official_docs=official,
        refined_queries=unified.refined_queries,
        warnings=unified.warnings,
        profile="unified",
        source_hint=unified.source_hint,
        items=flat,
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


def _enrich_citation_snippet_task(citation_id: UUID, paper_payload: dict) -> None:
    from app.database import SessionLocal
    from app.models.citation import Citation

    db = SessionLocal()
    try:
        row = db.get(Citation, citation_id)
        if not row or (row.quotable_snippet or "").strip():
            return
        snippet, _ = fetch_paper_quotable_snippet(paper_payload)
        if snippet:
            row.quotable_snippet = snippet
            db.commit()
    finally:
        db.close()


@router.post("/{book_id}/literature/add-selected", response_model=CitationListOut)
def literature_add_selected(
    book_id: UUID,
    body: CitationBatchIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将用户勾选的检索结果加入本书（先保存元数据，摘录后台补全）。"""
    book = book_service.get_book_or_404(book_id, user, db)
    style = book.citation_style.value if book.citation_style else "apa"
    created: list = []
    for p in body.papers:
        payload = _paper_payload(p)
        row = create_citation_from_paper(
            db,
            book,
            payload,
            source=CitationSource.literature_search,
        )
        created.append(row)
        background_tasks.add_task(_enrich_citation_snippet_task, row.id, dict(payload))
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
    勾选文献 → 抓取可引用片段 → 加入本书 → 返回可插入正文的引用段落。
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
            source=src,
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

    return LiteratureInsertQuotesOut(
        quotes=quote_blocks,
        citations=[
            CitationOut.model_validate(r).model_copy(update={"formatted": formatted_line(r, style)})
            for r in citation_rows
        ],
    )
