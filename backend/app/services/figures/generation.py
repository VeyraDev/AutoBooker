"""FigureGenerationService — 配图 V2 统一生成入口。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.llm.providers import resolve_book_writing_model
from app.models.book import Book
from app.models.figure import Figure, FigureSource, FigureStatus, FigureType
from app.services.figures.pipeline.orchestrator import classify_and_persist
from app.services.figures.quality import FigureQualityReport, inspect_rendered_figure, merge_quality_reports
from app.services.figures.render.dispatcher import render_figure
from app.services.figures.storage.manager import figure_storage
from app.services.quality import QualityStatus


def chat_model_for_book(book: Book) -> str:
    return resolve_book_writing_model(book)


def figure_output_path(book_id: UUID, figure_id: UUID, *, chapter_index: int = 0) -> Path:
    return figure_storage.png_path(book_id, chapter_index, figure_id)


def public_url(book_id: UUID, chapter_index: int, figure_id: UUID, *, ext: str = "png") -> str:
    return figure_storage.public_url(book_id, chapter_index, figure_id, ext=ext)


def _classification(fig: Figure) -> dict:
    return dict(fig.classification_json) if isinstance(fig.classification_json, dict) else {}


def _set_quality_report(fig: Figure, report: dict) -> None:
    clf = _classification(fig)
    clf["quality_report"] = report
    fig.classification_json = clf


def _blocking_quality_status(report: dict | None) -> bool:
    status = str((report or {}).get("status") or "")
    return status in {QualityStatus.failed.value, QualityStatus.needs_clarification.value}


def _render_exception_report(exc: Exception) -> dict:
    return FigureQualityReport(
        status=QualityStatus.failed.value,
        render_score=0.0,
        failures=["render_exception"],
        recommendations=[str(exc)],
        evidence={"exception_type": type(exc).__name__},
    ).to_dict()


def _cleanup_candidates(*paths: Path | None) -> None:
    for path in paths:
        if path and path.is_file():
            path.unlink()


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

    initial_report = _classification(fig).get("quality_report")
    if _blocking_quality_status(initial_report):
        fig.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(fig)
        return fig

    if (fig.renderer or "").strip().lower() == "need_data":
        raise ValueError("数据图缺少可解析的数值，请编辑标注后重试")

    chapter_id = fig.chapter_index
    out_path = figure_output_path(book.id, fig.id, chapter_index=chapter_id)
    svg_path = figure_storage.svg_path(book.id, chapter_id, fig.id)
    candidate_base = out_path.with_name(f".candidate-{uuid.uuid4().hex}")
    candidate_png = candidate_base.with_suffix(".png")
    candidate_svg = candidate_base.with_suffix(".svg")

    model = chat_model_for_book(book)
    try:
        render_result = render_figure(fig, book, candidate_png, model=model, chart_type=chart_type)
        png = render_result.primary_png_path
        rendered_svg = render_result.optional_svg_path
        render_report = inspect_rendered_figure(
            png_path=png,
            svg_path=rendered_svg,
            classification=_classification(fig),
        )
    except Exception as exc:
        render_result = None
        png = None
        rendered_svg = None
        render_report = _render_exception_report(exc)

    clf = _classification(fig)
    merged_report = merge_quality_reports(clf.get("quality_report"), render_report)
    _set_quality_report(fig, merged_report)

    if str(merged_report.get("status")) == QualityStatus.failed.value:
        _cleanup_candidates(png, rendered_svg, candidate_png, candidate_svg)
        fig.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(fig)
        return fig

    has_png = bool(png and png.is_file())
    has_svg = bool(rendered_svg and rendered_svg.is_file())
    if not has_png and not has_svg:
        _cleanup_candidates(rendered_svg, candidate_png, candidate_svg)
        fig.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(fig)
        return fig

    if has_png:
        if out_path.is_file():
            out_path.unlink()
        png.replace(out_path)
    elif out_path.is_file():
        out_path.unlink()

    if has_svg:
        if svg_path.is_file():
            svg_path.unlink()
        rendered_svg.replace(svg_path)
    elif svg_path.is_file():
        svg_path.unlink()

    if False:
        raise RuntimeError(f"图表文件未写入: {png}")

    clf = _classification(fig)
    figure_storage.save_assets(
        book_id=book.id,
        chapter_id=chapter_id,
        figure_id=fig.id,
        dsl=clf.get("dsl_json"),
        meta={
            "figure_id": str(fig.id),
            "book_id": str(book.id),
            "chapter_id": chapter_id,
            "source_prompt": description,
            "diagram_type": clf.get("diagram_type") or clf.get("diagram_subtype"),
            "renderer": fig.renderer,
            "render_diagnostics": getattr(render_result, "diagnostics", {}) if render_result else {},
            "quality_report": clf.get("quality_report"),
            "version": 1,
        },
    )

    fig.render_source = render_result.render_source if render_result else ""
    if has_svg:
        fig.svg_url = public_url(book.id, chapter_id, fig.id, ext="svg")
        fig.file_path = str(svg_path.resolve())
        fig.file_url = (
            public_url(book.id, chapter_id, fig.id, ext="png")
            if has_png
            else fig.svg_url
        )
    else:
        fig.svg_url = None
        fig.file_path = str(out_path.resolve())
        fig.file_url = public_url(book.id, chapter_id, fig.id, ext="png")
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
    dest = figure_storage.png_path(book_id, fig.chapter_index, fig.id)
    if ext != ".png":
        dest = dest.with_suffix(ext)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    old_svg = figure_storage.svg_path(book_id, fig.chapter_index, fig.id)
    if old_svg.is_file():
        old_svg.unlink()
    fig.file_path = str(dest)
    fig.file_url = public_url(book_id, fig.chapter_index, fig.id, ext=dest.suffix.lstrip("."))
    fig.svg_url = None
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
