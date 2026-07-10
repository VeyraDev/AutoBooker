"""FigureGenerationService — 配图 V2 统一生成入口。"""

from __future__ import annotations

import tempfile
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
from app.services.figures.critic.layout_critic import run_layout_critic
from app.services.figures.critic.structural import run_structural_critic
from app.services.figures.quality import FigureQualityReport, inspect_rendered_figure, merge_quality_reports
from app.services.figures.render.dispatcher import render_figure
from app.services.figures.storage.manager import figure_storage
from app.services.quality import QualityStatus


class FigureGenerationError(ValueError):
    """渲染链路未产出可用图像文件。"""

    def __init__(self, message: str, *, quality_report: dict | None = None) -> None:
        super().__init__(message)
        self.quality_report = quality_report or {}


def chat_model_for_book(book: Book, user=None, db=None) -> str:
    return resolve_book_writing_model(book, user=user, db=db)


def figure_output_path(book_id: UUID, figure_id: UUID, *, chapter_index: int = 0) -> Path:
    return figure_storage.png_path(book_id, chapter_index, figure_id)


def public_url(book_id: UUID, chapter_index: int, figure_id: UUID, *, ext: str = "png") -> str:
    return figure_storage.public_url(book_id, chapter_index, figure_id, ext=ext)


def sync_figure_urls_from_assets(fig: Figure, db: Session) -> None:
    from app.services.assets.asset_resolver import AssetResolver

    AssetResolver(db).sync_figure_urls_from_assets(fig)


def sync_figure_urls_from_disk(fig: Figure, *, chapter_index: int | None = None) -> None:
    """根据磁盘上的规范路径同步 file_path / file_url / svg_url。"""
    ch = chapter_index if chapter_index is not None else fig.chapter_index
    png_path = figure_storage.png_path(fig.book_id, ch, fig.id)
    svg_path = figure_storage.svg_path(fig.book_id, ch, fig.id)
    has_png = png_path.is_file()
    has_svg = svg_path.is_file()
    if has_svg:
        fig.svg_url = public_url(fig.book_id, ch, fig.id, ext="svg")
        fig.file_path = str(svg_path.resolve())
        fig.file_url = public_url(fig.book_id, ch, fig.id, ext="png") if has_png else fig.svg_url
    elif has_png:
        fig.svg_url = None
        fig.file_path = str(png_path.resolve())
        fig.file_url = public_url(fig.book_id, ch, fig.id, ext="png")
    return None


def _classification(fig: Figure) -> dict:
    return dict(fig.classification_json) if isinstance(fig.classification_json, dict) else {}


def _set_quality_report(fig: Figure, report: dict) -> None:
    clf = _classification(fig)
    clf["quality_report"] = report
    fig.classification_json = clf


def _render_failure_message(report: dict | None, *, default: str = "渲染未产出图像文件") -> str:
    report = report or {}
    failures = [str(x) for x in (report.get("failures") or []) if str(x).strip()]
    if "render_exception" in failures:
        recs = report.get("recommendations") or []
        if recs:
            return f"图表渲染失败：{recs[0]}"
    return default


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
        model=chat_model_for_book(book, db=db),
        use_llm=True,
    )

    chapter_id = fig.chapter_index
    with tempfile.TemporaryDirectory(prefix="figure-render-") as tmpdir:
        tmp = Path(tmpdir)
        candidate_png = tmp / f"candidate-{uuid.uuid4().hex}.png"
        candidate_svg = tmp / f"candidate-{uuid.uuid4().hex}.svg"

        model = chat_model_for_book(book, db=db)
        render_result = None
        png: Path | None = None
        rendered_svg: Path | None = None
        try:
            render_result = render_figure(fig, book, candidate_png, model=model, chart_type=chart_type)
            png = render_result.primary_png_path
            rendered_svg = render_result.optional_svg_path
            clf = _classification(fig)
            render_report = inspect_rendered_figure(
                png_path=png,
                svg_path=rendered_svg,
                classification=clf,
            )
            qr_evidence = (clf.get("quality_report") or {}).get("evidence") or {}
            structural = clf.get("structural_critic") or qr_evidence.get("structural_critic") or run_structural_critic(
                semantic_ir=clf.get("semantic_ir"),
                dsl_json=clf.get("dsl_json"),
                parsed_spec=clf.get("parsed_spec"),
                source_text=description,
            )
            layout_critic = run_layout_critic(
                layout_result=clf.get("layout_result"),
                svg_path=rendered_svg,
                classification=clf,
            )
            render_report = merge_quality_reports(
                render_report,
                {
                    "status": structural.get("status"),
                    "semantic_score": structural.get("alignment_rate", 1.0),
                    "layout_score": layout_critic.get("layout_score", 1.0),
                    "failures": structural.get("failures", []) + layout_critic.get("failures", []),
                    "warnings": structural.get("warnings", []) + layout_critic.get("warnings", []),
                    "recommendations": structural.get("recommendations", []) + layout_critic.get("recommendations", []),
                    "evidence": {"structural_critic": structural, "layout_critic": layout_critic},
                },
            )
        except Exception as exc:
            render_report = _render_exception_report(exc)

        has_png = bool(png and png.is_file())
        has_svg = bool(rendered_svg and rendered_svg.is_file())
        if not has_png and not has_svg:
            clf = _classification(fig)
            merged_report = merge_quality_reports(clf.get("quality_report"), render_report)
            _set_quality_report(fig, merged_report)
            fig.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(fig)
            raise FigureGenerationError(
                _render_failure_message(merged_report),
                quality_report=merged_report,
            )

        from app.models.binary_asset import FigureAssetRole
        from app.services.assets.figure_asset_service import FigureAssetService

        owner_user_id = book.user_id
        fas = FigureAssetService(db)
        if has_png:
            fas.attach_asset(
                figure=fig,
                content=png.read_bytes(),
                filename=f"{fig.id.hex}.png",
                mime_type="image/png",
                owner_user_id=owner_user_id,
                role=FigureAssetRole.png,
                set_primary_url=True,
            )
        if has_svg:
            fas.attach_asset(
                figure=fig,
                content=rendered_svg.read_bytes(),
                filename=f"{fig.id.hex}.svg",
                mime_type="image/svg+xml",
                owner_user_id=owner_user_id,
                role=FigureAssetRole.svg,
            )

        clf = _classification(fig)
        merged_report = merge_quality_reports(clf.get("quality_report"), render_report)
        _set_quality_report(fig, merged_report)
        parsed_spec = clf.get("parsed_spec") if isinstance(clf.get("parsed_spec"), dict) else {}
        clf["render_meta"] = {
            "figure_id": str(fig.id),
            "book_id": str(book.id),
            "chapter_id": chapter_id,
            "source_prompt": description,
            "diagram_type": clf.get("diagram_type") or clf.get("diagram_subtype"),
            "graph_visual_grammar": parsed_spec.get("graph_visual_grammar"),
            "mandatory_semantics": parsed_spec.get("mandatory_semantics"),
            "renderer": fig.renderer,
            "render_diagnostics": getattr(render_result, "diagnostics", {}) if render_result else {},
            "quality_report": clf.get("quality_report"),
            "version": int(datetime.now(timezone.utc).timestamp()),
        }
        fig.classification_json = clf

        fig.render_source = render_result.render_source if render_result else ""
        sync_figure_urls_from_assets(fig, db)
        fig.status = FigureStatus.generated
        fig.updated_at = datetime.now(timezone.utc)
        if not fig.caption:
            first = description.split("。")[0].strip() or description
            fig.caption = (first[:120] + "…") if len(first) > 120 else first
        db.commit()
        db.refresh(fig)
        return fig


def save_uploaded_figure(fig: Figure, book_id: UUID, content: bytes, filename: str, db: Session, *, owner_user_id) -> Figure:
    from app.models.binary_asset import FigureAssetRole
    from app.services.assets.figure_asset_service import FigureAssetService

    ext = Path(filename).suffix.lower() or ".png"
    mime = "image/png"
    if ext in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif ext == ".webp":
        mime = "image/webp"
    elif ext == ".gif":
        mime = "image/gif"
    FigureAssetService(db).set_primary_asset(
        figure=fig,
        content=content,
        filename=filename,
        mime_type=mime,
        owner_user_id=owner_user_id,
        role=FigureAssetRole.primary,
    )
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
