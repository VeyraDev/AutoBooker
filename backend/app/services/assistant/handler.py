"""Unified AI assistant handler."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.llm.client import LLMClient
from app.models.book import Book
from app.models.chapter import Chapter
from app.models.figure import Figure, FigureType
from app.services.assistant.context import AssistantContext
from app.services.assistant.intent import classify_intent
from app.services.assistant.prompt_builder import build_execution_prompt
from app.services.figure_generate import (
    create_figure_from_annotation,
    generate_figure_asset,
    _chat_model_for_book,
)
from app.services.figure_service import get_figure_or_404


IMAGE_INTENTS = frozenset({"gen_flowchart", "gen_chart", "gen_figure", "regen_figure"})


def _chat_model(book: Book) -> str:
    return _chat_model_for_book(book)


async def execute_text_processing(
    intent: dict,
    system: str,
    user: str,
    book: Book,
) -> dict:
    client = LLMClient()
    out = client.chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=_chat_model(book),
        max_tokens=4096,
        temperature=0.45,
    )
    return {"type": "text", "content": out.strip(), "intent": intent.get("intent")}


async def execute_image_generation(
    intent: dict,
    ctx: AssistantContext,
    book: Book,
    chapter_index: int,
    db: Session,
    params: dict,
) -> dict:
    figure_id = ctx.figure_id
    i = intent.get("intent", "")

    if figure_id:
        fig = get_figure_or_404(UUID(figure_id), book.id, db)
    else:
        type_map = {
            "gen_flowchart": FigureType.flowchart,
            "gen_chart": FigureType.chart,
            "gen_figure": FigureType.figure,
        }
        ftype = type_map.get(i, FigureType.figure)
        if i == "regen_figure":
            ftype = FigureType.figure
        desc = params.get("_description") or ctx.user_text or ctx.selected_text or ""
        fig = create_figure_from_annotation(
            book.id, chapter_index, ftype, desc, db
        )

    if i == "gen_flowchart":
        fig.figure_type = FigureType.flowchart
    elif i == "gen_chart":
        fig.figure_type = FigureType.chart
    elif i == "gen_figure":
        fig.figure_type = FigureType.figure
    elif i == "regen_figure" and figure_id:
        pass  # 保留原 figure_type

    db.commit()
    fig = generate_figure_asset(
        fig,
        book,
        db,
        chart_type=params.get("chart_type"),
        sub_kind=params.get("sub_kind"),
        intent=i,
    )
    return {
        "type": "figure",
        "figure_id": str(fig.id),
        "file_url": fig.file_url,
        "figure_number": fig.figure_number,
        "status": fig.status.value,
        "caption": fig.caption,
        "figure_type": fig.figure_type.value,
        "updated_at": fig.updated_at.isoformat() if fig.updated_at else None,
        "intent": i,
    }


async def handle_assistant_request(
    user_text: str,
    selected_text: str | None,
    figure_id: str | None,
    cursor_paragraph: str | None,
    explicit_intent: str | None,
    book_id: UUID,
    chapter_index: int,
    db: Session,
    *,
    chart_type: str | None = None,
    sub_kind: str | None = None,
) -> dict:
    book = db.get(Book, book_id)
    if not book:
        from fastapi import HTTPException, status

        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")

    chapter = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
        .first()
    )
    figure = db.get(Figure, UUID(figure_id)) if figure_id else None

    ctx = AssistantContext(
        user_text=user_text or "",
        selected_text=selected_text,
        book_type=book.book_type.value if book.book_type else "",
        style_type=book.style_type or "",
        chapter_title=chapter.title if chapter else "",
        chapter_summary=(chapter.summary or "") if chapter else "",
        cursor_paragraph=cursor_paragraph or "",
        figure_id=figure_id,
        figure_annotation=figure.raw_annotation if figure else None,
        explicit_intent=explicit_intent,
    )

    intent = classify_intent(ctx)
    if intent.get("needs_confirmation") and not explicit_intent:
        return {
            "type": "confirm",
            "message": "请确认您希望执行的操作：生成流程图、数据图、插图，还是文字编辑？",
            "intent": intent.get("intent"),
            "confidence": intent.get("confidence"),
            "candidates": intent.get("confirmation_candidates") or [],
        }
    if intent.get("extracted_params"):
        ep = intent["extracted_params"]
        if ep.get("sub_kind") and not sub_kind:
            sub_kind = ep.get("sub_kind")
    system, user, params = build_execution_prompt(intent, ctx)
    if chart_type:
        params["chart_type"] = chart_type
    if sub_kind:
        params["sub_kind"] = sub_kind

    if intent.get("intent") in IMAGE_INTENTS or explicit_intent in IMAGE_INTENTS:
        return await execute_image_generation(
            intent, ctx, book, chapter_index, db, params
        )
    return await execute_text_processing(intent, system, user, book)
