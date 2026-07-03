from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.book import Book
from app.models.figure import Figure, FigureStatus, FigureType
from app.models.figure_batch import FigureBatchItem, FigureBatchRun
from app.services.figures.generation import generate_figure_asset

logger = logging.getLogger(__name__)


def create_figure_batch(
    db: Session,
    book_id: UUID,
    *,
    chapter_index: int | None = None,
    trigger: str = "manual",
) -> FigureBatchRun:
    query = db.query(Figure).filter(
        Figure.book_id == book_id,
        Figure.status == FigureStatus.pending,
        Figure.figure_type != FigureType.screenshot,
        Figure.file_path.is_(None),
        Figure.file_url.is_(None),
    )
    if chapter_index is not None:
        query = query.filter(Figure.chapter_index == chapter_index)
    active_ids = [
        row[0]
        for row in db.query(FigureBatchItem.figure_id)
        .filter(FigureBatchItem.status.in_(("pending", "running")))
        .all()
    ]
    if active_ids:
        query = query.filter(~Figure.id.in_(active_ids))
    figures = (
        query.order_by(Figure.chapter_index, Figure.sort_order, Figure.created_at)
        .with_for_update(of=Figure, skip_locked=True)
        .all()
    )
    run = FigureBatchRun(
        book_id=book_id,
        chapter_index=chapter_index,
        trigger=trigger,
        total=len(figures),
        status="pending" if figures else "completed",
        finished_at=None if figures else datetime.now(timezone.utc),
    )
    db.add(run)
    db.flush()
    for figure in figures:
        db.add(FigureBatchItem(run_id=run.id, figure_id=figure.id))
    db.commit()
    db.refresh(run)
    return run


def _generate_item(item_id: UUID) -> bool:
    db = SessionLocal()
    try:
        item = db.get(FigureBatchItem, item_id)
        if not item or item.status != "pending":
            return False
        item.status = "running"
        db.commit()
        figure = db.get(Figure, item.figure_id)
        if not figure or figure.status != FigureStatus.pending or figure.file_path or figure.file_url:
            item.status = "skipped"
            item.finished_at = datetime.now(timezone.utc)
            db.commit()
            return True
        if figure.figure_type == FigureType.screenshot:
            item.status = "skipped"
            item.finished_at = datetime.now(timezone.utc)
            db.commit()
            return True
        book = db.get(Book, figure.book_id)
        if not book:
            raise RuntimeError("book not found")
        generate_figure_asset(figure, book, db)
        item.status = "completed"
        item.finished_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as exc:
        logger.warning("figure batch item failed item=%s: %s", item_id, exc, exc_info=True)
        db.rollback()
        item = db.get(FigureBatchItem, item_id)
        if item:
            item.status = "failed"
            item.error_message = str(exc)[:1000]
            item.finished_at = datetime.now(timezone.utc)
            db.commit()
        return False
    finally:
        db.close()


def run_figure_batch(run_id: UUID) -> None:
    db = SessionLocal()
    try:
        run = db.get(FigureBatchRun, run_id)
        if not run or run.status not in {"pending", "running"}:
            return
        run.status = "running"
        db.commit()
        item_ids = [
            row[0]
            for row in db.query(FigureBatchItem.id)
            .filter(FigureBatchItem.run_id == run_id, FigureBatchItem.status == "pending")
            .all()
        ]
    finally:
        db.close()
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="figure-batch") as executor:
        futures = [executor.submit(_generate_item, item_id) for item_id in item_ids]
        for _ in as_completed(futures):
            progress_db = SessionLocal()
            try:
                run = progress_db.get(FigureBatchRun, run_id)
                if run:
                    statuses = [
                        row[0]
                        for row in progress_db.query(FigureBatchItem.status)
                        .filter(FigureBatchItem.run_id == run_id)
                        .all()
                    ]
                    run.completed = sum(x in {"completed", "skipped"} for x in statuses)
                    run.failed = sum(x == "failed" for x in statuses)
                    progress_db.commit()
            finally:
                progress_db.close()
    db = SessionLocal()
    try:
        run = db.get(FigureBatchRun, run_id)
        if not run:
            return
        statuses = [
            row[0]
            for row in db.query(FigureBatchItem.status).filter(FigureBatchItem.run_id == run_id).all()
        ]
        run.completed = sum(x in {"completed", "skipped"} for x in statuses)
        run.failed = sum(x == "failed" for x in statuses)
        if run.status != "paused":
            run.status = "completed" if not run.failed else "completed_with_errors"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def pause_figure_batch(db: Session, run: FigureBatchRun) -> FigureBatchRun:
    if run.status not in {"pending", "running"}:
        return run
    now = datetime.now(timezone.utc)
    run.status = "paused"
    run.finished_at = now
    (
        db.query(FigureBatchItem)
        .filter(
            FigureBatchItem.run_id == run.id,
            FigureBatchItem.status == "pending",
        )
        .update(
            {
                FigureBatchItem.status: "paused",
                FigureBatchItem.finished_at: now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    db.refresh(run)
    return run


def enqueue_auto_chapter_figures(book_id: UUID, chapter_index: int) -> UUID | None:
    db = SessionLocal()
    try:
        run = create_figure_batch(db, book_id, chapter_index=chapter_index, trigger="auto_book")
        return run.id if run.total else None
    finally:
        db.close()
