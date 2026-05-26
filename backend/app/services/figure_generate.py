"""Generate figure assets and update DB records."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.llm.providers import resolve_book_ai_model
from app.models.book import Book
from app.models.figure import Figure, FigureStatus, FigureType
from app.services.figure_render.chart import generate_chart
from app.services.figure_render.figure_ai import generate_figure_image
from app.services.figure_render.flowchart import generate_flowchart


def _chat_model_for_book(book: Book) -> str:
    """与章节生成一致，保留 provider:model 供 LLMClient 路由。"""
    return resolve_book_ai_model(book)


def _figure_output_path(book_id: UUID, figure_id: UUID) -> Path:
    base = settings.figures_path / str(book_id)
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{figure_id.hex}.png"


def _public_url(book_id: UUID, filename: str) -> str:
    return f"/static/figures/{book_id}/{filename}"


def generate_figure_asset(
    fig: Figure,
    book: Book,
    db: Session,
    *,
    chart_type: str | None = None,
    sub_kind: str | None = None,
) -> Figure:
    if fig.figure_type == FigureType.screenshot:
        raise ValueError("screenshot 类型仅支持上传，不支持自动生成")

    description = (fig.raw_annotation or fig.caption or "").strip()
    if not description:
        raise ValueError("缺少图片描述")

    out_path = _figure_output_path(book.id, fig.id)
    if out_path.is_file():
        out_path.unlink()
    model = _chat_model_for_book(book)
    render_source = ""

    if fig.figure_type == FigureType.flowchart:
        render_source, png = generate_flowchart(
            description,
            out_path,
            model=model,
            book_type=book.book_type.value if book.book_type else "",
        )
    elif fig.figure_type == FigureType.chart:
        render_source, png = generate_chart(
            description,
            out_path,
            model=model,
            chart_type_hint=chart_type,
        )
    elif fig.figure_type == FigureType.figure:
        render_source, png = generate_figure_image(
            description,
            out_path,
            style_type=book.style_type or "",
            sub_kind=sub_kind or "figure",
        )
    else:
        raise ValueError(f"不支持的图表类型: {fig.figure_type}")

    if not png.is_file():
        raise RuntimeError(f"图表文件未写入: {png}")

    fig.render_source = render_source
    fig.file_path = str(png.resolve())
    fig.file_url = _public_url(book.id, png.name)
    fig.status = FigureStatus.generated
    fig.updated_at = datetime.now(timezone.utc)
    if not fig.caption:
        first = description.split("。")[0].strip() or description
        fig.caption = (first[:120] + "…") if len(first) > 120 else first
    db.commit()
    db.refresh(fig)
    return fig


def save_uploaded_figure(fig: Figure, book_id: UUID, content: bytes, filename: str, db: Session) -> Figure:
    ext = Path(filename).suffix.lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        ext = ".png"
    base = settings.figures_path / str(book_id)
    base.mkdir(parents=True, exist_ok=True)
    name = f"{fig.id.hex}{ext}"
    dest = base / name
    dest.write_bytes(content)
    fig.file_path = str(dest)
    fig.file_url = _public_url(book_id, name)
    fig.status = FigureStatus.uploaded
    fig.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(fig)
    return fig


def create_figure_from_annotation(
    book_id: UUID,
    chapter_index: int,
    figure_type: FigureType,
    raw_annotation: str,
    db: Session,
    *,
    sort_order: int = 0,
) -> Figure:
    fig = Figure(
        id=uuid.uuid4(),
        book_id=book_id,
        chapter_index=chapter_index,
        figure_type=figure_type,
        status=FigureStatus.pending,
        raw_annotation=raw_annotation.strip(),
        sort_order=sort_order,
    )
    db.add(fig)
    db.commit()
    db.refresh(fig)
    from app.services.figure_service import renumber_figures

    renumber_figures(book_id, db)
    db.refresh(fig)
    return fig
