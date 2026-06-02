"""FigureGenerationService — 配图 V2 统一生成入口。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.llm.providers import resolve_book_ai_model
from app.models.book import Book
from app.models.figure import Figure, FigureSource, FigureStatus, FigureType
from app.services.figures.pipeline.orchestrator import classify_and_persist
from app.services.figures.render.dispatcher import render_figure
from app.services.figures.render.svg_export import public_svg_url, svg_path_for_png


def chat_model_for_book(book: Book) -> str:
    return resolve_book_ai_model(book)


def figure_output_path(book_id: UUID, figure_id: UUID) -> Path:
    base = settings.figures_path / str(book_id)
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{figure_id.hex}.png"


def public_url(book_id: UUID, filename: str) -> str:
    return f"/static/figures/{book_id}/{filename}"


def generate_figure_asset(
    fig: Figure,
    book: Book,
    db: Session,
    *,
    chart_type: str | None = None,
    user_hint: str = "",
    chapter_title: str = "",
    legacy_tag: str | None = None,
    sub_kind: str | None = None,
) -> Figure:
    if fig.figure_type == FigureType.screenshot:
        raise ValueError("screenshot 类型仅支持上传，不支持自动生成")

    if sub_kind:
        fig.subtype = sub_kind
        db.commit()
        db.refresh(fig)

    description = (fig.raw_annotation or fig.caption or "").strip()
    if not description:
        raise ValueError("缺少图片描述")

    if not chapter_title:
        from app.models.chapter import Chapter

        ch = db.query(Chapter).filter_by(book_id=book.id, index=fig.chapter_index).first()
        chapter_title = ch.title if ch else ""

    classify_and_persist(
        fig,
        db,
        style_type=book.style_type,
        book_type=book.book_type.value if book.book_type else "",
        chapter_title=chapter_title,
        legacy_tag=legacy_tag,
        user_hint=user_hint,
        model=chat_model_for_book(book),
        use_llm=True,
    )

    if (fig.renderer or "").strip().lower() == "need_data":
        raise ValueError("数据图缺少可解析的数值，请编辑标注后重试")

    out_path = figure_output_path(book.id, fig.id)
    svg_path = svg_path_for_png(out_path)
    for p in (out_path, svg_path):
        if p.is_file():
            p.unlink()

    model = chat_model_for_book(book)
    render_source, png = render_figure(fig, book, out_path, model=model, chart_type=chart_type)

    if not png.is_file():
        raise RuntimeError(f"图表文件未写入: {png}")

    fig.render_source = render_source
    fig.file_path = str(png.resolve())
    fig.file_url = public_url(book.id, png.name)
    if svg_path.is_file():
        fig.svg_url = public_svg_url(book.id, fig.id.hex)
    else:
        fig.svg_url = None
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
    fig.file_url = public_url(book_id, name)
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
    figure_source: FigureSource = FigureSource.writing,
) -> Figure:
    fig = Figure(
        id=uuid.uuid4(),
        book_id=book_id,
        chapter_index=chapter_index,
        figure_type=figure_type,
        status=FigureStatus.pending,
        raw_annotation=raw_annotation.strip(),
        sort_order=sort_order,
        figure_source=figure_source,
    )
    db.add(fig)
    db.commit()
    db.refresh(fig)
    from app.services.figure_service import renumber_figures

    renumber_figures(book_id, db)
    db.refresh(fig)
    return fig
