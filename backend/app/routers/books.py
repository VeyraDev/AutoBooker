import re
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.book import (
    BookCreate,
    BookDuplicateIn,
    BookDuplicateOut,
    BookOut,
    BookUpdate,
    ExportPreviewIn,
    ExportPreviewOut,
    SetupRecommendIn,
    SetupRecommendOut,
)
from app.services import book_service, export_service
from app.services.setup_recommend_service import recommend_book_setup

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookOut])
def list_books(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return book_service.list_user_books(user, db)


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def create_book(
    body: BookCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return book_service.create_book(user, body.model_dump(mode="json", exclude_unset=False), db)


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return book_service.get_book_or_404(book_id, user, db)


@router.put("/{book_id}", response_model=BookOut)
def update_book(
    book_id: UUID,
    body: BookUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    return book_service.update_book(book, body.model_dump(exclude_unset=True, mode="json"), db)


@router.post("/{book_id}/setup-recommend", response_model=SetupRecommendOut)
def setup_recommend(
    book_id: UUID,
    body: SetupRecommendIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    force = bool(body.force) if body else False
    try:
        result = recommend_book_setup(book, user, db, force=force)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"书稿设定推荐失败：{exc}",
        ) from exc
    return SetupRecommendOut(**result)


@router.post("/{book_id}/duplicate", response_model=BookDuplicateOut, status_code=status.HTTP_201_CREATED)
def duplicate_book(
    book_id: UUID,
    body: BookDuplicateIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    source = book_service.get_book_or_404(book_id, user, db)
    copy_outline = bool(body.copy_outline) if body else False
    new_book, message = book_service.duplicate_book(source, user, db, copy_outline=copy_outline)
    return BookDuplicateOut(book=BookOut.model_validate(new_book), message=message)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    book_service.delete_book(book, db)
    return None


@router.get("/{book_id}/export/notice")
def export_notice(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    from app.services.review_stage.review_stage_service import ReviewStageService

    summary = ReviewStageService(db).summary(book_id) or {}
    count = int(summary.get("suggestion_count") or 0)
    return {
        "suggestion_count": count,
        "message": (
            f"当前书稿还有 {count} 条审校建议未处理。审校建议不会影响导出，你可以继续导出或返回处理。"
            if count
            else None
        ),
    }


@router.get("/{book_id}/export/preview", response_model=ExportPreviewOut)
def export_preview(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.publication.export_preview import build_export_preview

    return ExportPreviewOut(**build_export_preview(book_id, user, db))


@router.post("/{book_id}/export/preview", response_model=ExportPreviewOut)
def export_preview_with_info(
    book_id: UUID,
    body: ExportPreviewIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用临时封面信息刷新预览；persist=true 时写入 publication_info。"""
    from app.services.publication.export_preview import build_export_preview
    from app.services.publication.publication_info import normalize_publication_info

    payload = body or ExportPreviewIn()
    pub = payload.publication_info
    book = book_service.get_book_or_404(book_id, user, db)
    if isinstance(pub, dict) and payload.regenerate_cover_bg:
        from app.services.publication.cover_background import regenerate_cover_background_for_book

        pub = regenerate_cover_background_for_book(
            db,
            book_id=book.id,
            owner_user_id=user.id,
            publication=pub,
            fallback_title=book.title,
        )
        # AI 封面生成成本高，背景 asset 始终落库，避免刷新丢失
        book_service.update_book(
            book,
            {
                "publication_info": normalize_publication_info(pub, fallback_title=book.title),
            },
            db,
        )
        db.refresh(book)
    elif payload.persist and isinstance(pub, dict):
        book_service.update_book(
            book,
            {
                "publication_info": normalize_publication_info(pub, fallback_title=book.title),
            },
            db,
        )
        db.refresh(book)
    return ExportPreviewOut(
        **build_export_preview(
            book_id,
            user,
            db,
            publication_info=pub if isinstance(pub, dict) else None,
        )
    )


@router.get("/{book_id}/export")
def export_book(
    book_id: UUID,
    format: str = Query(
        "markdown",
        description="导出格式：markdown / md / docx / pdf",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    body, filename, media_type = export_service.export_book_bytes(book_id, format, user, db)
    ascii_name = re.sub(r'[^\x20-\x7E]', "_", filename) or "export"
    cd = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(content=body, media_type=media_type, headers={"Content-Disposition": cd})
