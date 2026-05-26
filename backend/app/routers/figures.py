"""Figure CRUD, generate, upload, sync."""

from __future__ import annotations

import time
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.chapter import Chapter
from app.models.figure import FigureStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.figure import (
    FigureCaptionIn,
    FigureGenerateIn,
    FigureListItem,
    FigureListOut,
    FigureOut,
    FigureRefreshIn,
    FigureRefreshOut,
    FigureSyncOut,
)
from app.services import book_service
from app.services.figure_generate import generate_figure_asset, save_uploaded_figure
from app.services.figure_service import (
    get_figure_list,
    get_figure_or_404,
    refresh_chapter_figures,
    repair_figure_file,
    sync_figures_to_tiptap,
)

router = APIRouter(prefix="/books", tags=["figures"])

ALLOWED_IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _figure_out(fig) -> FigureOut:
    return FigureOut(
        id=fig.id,
        book_id=fig.book_id,
        chapter_index=fig.chapter_index,
        figure_number=fig.figure_number,
        figure_type=fig.figure_type.value,
        status=fig.status.value,
        caption=fig.caption,
        raw_annotation=fig.raw_annotation,
        file_url=fig.file_url,
        position_hint=fig.position_hint,
        sort_order=fig.sort_order,
        updated_at=fig.updated_at,
    )


@router.get("/{book_id}/figures", response_model=FigureListOut)
def list_figures(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    items = [FigureListItem(**row) for row in get_figure_list(book_id, db)]
    return FigureListOut(items=items)


@router.get("/{book_id}/figures/{figure_id}", response_model=FigureOut)
def get_figure(
    book_id: UUID,
    figure_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    fig = get_figure_or_404(figure_id, book_id, db)
    return _figure_out(fig)


@router.post("/{book_id}/figures/{figure_id}/generate", response_model=FigureOut)
def generate_figure(
    book_id: UUID,
    figure_id: UUID,
    body: FigureGenerateIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    fig = get_figure_or_404(figure_id, book_id, db)
    if fig.figure_type.value == "screenshot":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "截图类型请使用上传接口")
    opts = body or FigureGenerateIn()
    try:
        fig = generate_figure_asset(
            fig,
            book,
            db,
            chart_type=opts.chart_type,
            sub_kind=opts.sub_kind,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"生成失败: {e}") from e
    repair_figure_file(fig, db)
    return _figure_out(fig)


@router.post("/{book_id}/figures/{figure_id}/upload", response_model=FigureOut)
async def upload_figure(
    book_id: UUID,
    figure_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    fig = get_figure_or_404(figure_id, book_id, db)
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 png/jpg/webp/gif")
    content = await file.read()
    fig = save_uploaded_figure(fig, book_id, content, file.filename, db)
    return _figure_out(fig)


@router.patch("/{book_id}/figures/{figure_id}/approve", response_model=FigureOut)
def approve_figure(
    book_id: UUID,
    figure_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    fig = get_figure_or_404(figure_id, book_id, db)
    fig.status = FigureStatus.approved
    db.commit()
    db.refresh(fig)
    return _figure_out(fig)


@router.patch("/{book_id}/figures/{figure_id}/caption", response_model=FigureOut)
def update_caption(
    book_id: UUID,
    figure_id: UUID,
    body: FigureCaptionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    fig = get_figure_or_404(figure_id, book_id, db)
    fig.caption = body.caption.strip()
    db.commit()
    db.refresh(fig)
    return _figure_out(fig)


@router.post(
    "/{book_id}/chapters/{chapter_index}/figures/refresh",
    response_model=FigureRefreshOut,
)
def refresh_chapter_figures_route(
    book_id: UUID,
    chapter_index: int,
    body: FigureRefreshIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按 TipTap 中的 figureBlock 清理孤儿图并重编号，返回本章图表元数据。"""
    book_service.get_book_or_404(book_id, user, db)
    ch = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
        .first()
    )
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    meta = ch.content if isinstance(ch.content, dict) else {}
    tiptap = None
    if body and isinstance(body.tiptap_json, dict):
        tiptap = body.tiptap_json
    elif isinstance(meta.get("tiptap_json"), dict):
        tiptap = meta["tiptap_json"]
    figures = refresh_chapter_figures(book_id, chapter_index, tiptap, db)
    return FigureRefreshOut(items=[_figure_out(f) for f in figures])


@router.post(
    "/{book_id}/chapters/{chapter_index}/figures/sync",
    response_model=FigureSyncOut,
)
def sync_chapter_figures(
    book_id: UUID,
    chapter_index: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    ch = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
        .first()
    )
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    meta = ch.content if isinstance(ch.content, dict) else {}
    text = str(meta.get("text") or "")
    if not text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "章节无 text 内容可同步")
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            doc = sync_figures_to_tiptap(book_id, chapter_index, text, db)
            return FigureSyncOut(tiptap_json=doc)
        except OperationalError as e:
            last_err = e
            orig = getattr(e, "orig", None)
            if orig is None or getattr(orig, "pgcode", None) != "40P01":
                raise
            db.rollback()
            if attempt < 2:
                time.sleep(0.08 * (attempt + 1))
                continue
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "图表同步繁忙，请稍后重试",
            ) from e
    if last_err:
        raise last_err
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "图表同步失败")
