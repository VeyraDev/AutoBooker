"""Book format strategy API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.format_strategy import (
    FormatStrategyConfirmOut,
    FormatStrategyGenerateIn,
    FormatStrategyOut,
    FormatStrategyPatchIn,
)
from app.services import book_service
from app.services.writing.format_strategy_service import FormatStrategyService

router = APIRouter(prefix="/books", tags=["format-strategy"])


def get_format_strategy(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    svc = FormatStrategyService(db)
    strategy = svc.get_active(book_id)
    if not strategy:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No format strategy found")
    return strategy


@router.post("/{book_id}/format-strategy/generate", response_model=FormatStrategyOut)
def generate_format_strategy(
    book_id: UUID,
    body: FormatStrategyGenerateIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    body = body or FormatStrategyGenerateIn()
    svc = FormatStrategyService(db)
    try:
        strategy = svc.generate(book, force=body.force)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "栏目策略生成失败") from exc
    db.commit()
    db.refresh(strategy)
    return strategy


@router.patch("/{book_id}/format-strategy", response_model=FormatStrategyOut)
def patch_format_strategy(
    book_id: UUID,
    body: FormatStrategyPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    svc = FormatStrategyService(db)
    strategy = svc.get_draft(book.id) or svc.get_draft_or_create(book)
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty patch")
    try:
        strategy = svc.patch(strategy, patch)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    db.commit()
    db.refresh(strategy)
    return strategy


@router.post("/{book_id}/format-strategy/confirm", response_model=FormatStrategyConfirmOut)
def confirm_format_strategy(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    svc = FormatStrategyService(db)
    strategy = svc.get_draft(book.id)
    if not strategy:
        strategy = svc.get_draft_or_create(book)
    try:
        strategy = svc.confirm(book, strategy)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    db.commit()
    return FormatStrategyConfirmOut(strategy_id=strategy.id, status=strategy.status.value)
