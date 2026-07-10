"""Asset content API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.services import book_service
from app.services.assets.binary_asset_service import BinaryAssetService

router = APIRouter(prefix="/books", tags=["assets"])


@router.get("/{book_id}/assets/{asset_id}/content")
def get_asset_content(
    book_id: UUID,
    asset_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    content, mime, filename = BinaryAssetService(db).stream_asset(book_id=book_id, asset_id=asset_id)
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Cache-Control": "public, max-age=31536000, immutable",
    }
    return Response(content=content, media_type=mime, headers=headers)
