"""Unified AI assistant handler."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.providers import resolve_assistant_model
from app.models.book import Book
from app.models.chapter import Chapter
from app.models.user import User
from app.models.figure import Figure, FigureType
from app.services.assistant.context import AssistantContext
from app.services.assistant.intent import classify_intent
from app.services.assistant.prompt_builder import build_execution_prompt
from app.services.figures.generation import (
    create_figure_from_annotation,
    generate_figure_asset,
)
from app.services.figure_service import get_figure_or_404


IMAGE_INTENTS = frozenset({"gen_flowchart", "gen_chart", "gen_figure", "regen_figure"})


def _is_instruction_only(text: str) -> bool:
    t = (text or "").strip()
    if len(t) > 220:
        return False
    cues = ("帮我", "请", "改成", "换成", "重新", "生成", "画一", "左边", "右边", "中间", "不要", "层次")
    return any(c in t for c in cues)


async def execute_text_processing(
    intent: dict,
    system: str,
    user: str,
    *,
    chat_model: str,
) -> dict:
    client = LLMClient()
    out = client.chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=chat_model,
        max_tokens=4096,
        temperature=0.45,
    )
    return {"type": "text", "content": out.strip(), "intent": intent.get("intent")}


async def execute_image_generation(
    intent: dict,
    ctx: AssistantContext,
    book: Book,
    chapter: Chapter | None,
    chapter_index: int,
    db: Session,
    params: dict,
) -> dict:
    figure_id = ctx.figure_id
    i = intent.get("intent", "")

    user_hint = ""
    if figure_id:
        fig = get_figure_or_404(UUID(figure_id), book.id, db)
        new_desc = (params.get("_description") or ctx.user_text or "").strip()
        if new_desc and i in ("regen_figure", "gen_figure", "gen_flowchart", "gen_chart"):
            if _is_instruction_only(new_desc) and (fig.raw_annotation or "").strip():
                user_hint = new_desc
            else:
                fig.raw_annotation = new_desc[:2000]
                if not (fig.caption or "").strip():
                    fig.caption = new_desc[:500]
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
        from app.models.figure import FigureSource

        fig = create_figure_from_annotation(
            book.id,
            chapter_index,
            ftype,
            desc,
            db,
            figure_source=FigureSource.user_assistant,
        )
        if params.get("sub_kind") == "chapter_summary":
            fig.subtype = "chapter_summary"

    if i == "gen_flowchart":
        fig.figure_type = FigureType.flowchart
    elif i == "gen_chart":
        fig.figure_type = FigureType.chart
    elif i == "gen_figure":
        fig.figure_type = FigureType.figure

    db.commit()
    from app.services.figure_service import _LEGACY_TAG_BY_TYPE

    fig = generate_figure_asset(
        fig,
        book,
        db,
        chart_type=params.get("chart_type"),
        user_hint=user_hint or ctx.user_text or "",
        chapter_title=(chapter.title if chapter else ""),
        legacy_tag=_LEGACY_TAG_BY_TYPE.get(fig.figure_type),
    )
    clf = fig.classification_json if isinstance(fig.classification_json, dict) else {}
    return {
        "type": "figure",
        "figure_id": str(fig.id),
        "file_url": fig.file_url,
        "svg_url": fig.svg_url,
        "quality_report": clf.get("quality_report"),
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
    owner: User,
    *,
    chart_type: str | None = None,
    sub_kind: str | None = None,
) -> dict:
    from fastapi import HTTPException, status

    assistant_model = resolve_assistant_model(owner)
    book = db.get(Book, book_id)
    if not book:
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

    intent = classify_intent(ctx, model=assistant_model)
    if intent.get("needs_confirmation") and not explicit_intent:
        return {
            "type": "confirm",
            "message": "请确认您希望执行的操作：生成流程图、数据图、插图，还是文字编辑？",
            "intent": intent.get("intent"),
            "confidence": intent.get("confidence"),
            "candidates": intent.get("confirmation_candidates") or [],
        }
    system, user, params = build_execution_prompt(intent, ctx)
    if chart_type:
        params["chart_type"] = chart_type
    if sub_kind:
        params["sub_kind"] = sub_kind

    if intent.get("intent") in IMAGE_INTENTS or explicit_intent in IMAGE_INTENTS:
        return await execute_image_generation(
            intent, ctx, book, chapter, chapter_index, db, params
        )
    return await execute_text_processing(intent, system, user, chat_model=assistant_model)
