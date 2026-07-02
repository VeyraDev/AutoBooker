"""一键成书：章节正文完成后并行生成配图（不阻塞后续章节写作）。"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from uuid import UUID

from app.database import SessionLocal
from app.models.book import Book
from app.models.book_job import BookJob
from app.models.figure import Figure, FigureStatus, FigureType
from app.services.auto_book_job_progress import count_figure_progress, patch_job_checkpoint
from app.services.figures.generation import FigureGenerationError, generate_figure_asset

logger = logging.getLogger(__name__)

DEFAULT_FIGURE_WORKERS = 2


class AutoBookFigureWorker:
    def __init__(self, job_id: UUID, *, max_workers: int = DEFAULT_FIGURE_WORKERS) -> None:
        self.job_id = job_id
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="auto-book-fig")
        self._futures: list[Future] = []
        self._lock = threading.Lock()

    def enqueue_chapter(self, book_id: UUID, chapter_index: int) -> None:
        db = SessionLocal()
        try:
            pending = (
                db.query(Figure)
                .filter(
                    Figure.book_id == book_id,
                    Figure.chapter_index == chapter_index,
                    Figure.status == FigureStatus.pending,
                    Figure.figure_type != FigureType.screenshot,
                )
                .order_by(Figure.sort_order.asc(), Figure.created_at.asc())
                .all()
            )
            figure_ids = [fig.id for fig in pending]
        finally:
            db.close()

        for figure_id in figure_ids:
            future = self._executor.submit(_generate_one, book_id, figure_id, self.job_id)
            with self._lock:
                self._futures.append(future)

    def refresh_totals(self) -> None:
        db = SessionLocal()
        try:
            job = db.get(BookJob, self.job_id)
            if not job:
                return
            total, done, pending = count_figure_progress(db, job.book_id)
            patch_job_checkpoint(
                db,
                job,
                figures_total=total,
                figures_done=done,
                stage_message=f"图片：{done} / {total} 张完成" if total else None,
            )
        finally:
            db.close()

    def wait_all(self, timeout: float | None = None) -> None:
        with self._lock:
            futures = list(self._futures)
        for future in futures:
            try:
                future.result(timeout=timeout)
            except Exception:
                logger.exception("auto book figure task failed job=%s", self.job_id)
        self.refresh_totals()

    def shutdown(self, *, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)


def _generate_one(book_id: UUID, figure_id: UUID, job_id: UUID) -> None:
    db = SessionLocal()
    try:
        fig = db.get(Figure, figure_id)
        book = db.get(Book, book_id)
        if not fig or not book or fig.status != FigureStatus.pending:
            return
        if fig.figure_type == FigureType.screenshot:
            return
        generate_figure_asset(fig, book, db)
    except FigureGenerationError as exc:
        logger.warning("auto book figure failed book=%s figure=%s: %s", book_id, figure_id, exc)
    except Exception:
        logger.exception("auto book figure error book=%s figure=%s", book_id, figure_id)
    finally:
        db.close()
        _touch_figure_progress(job_id)


def _touch_figure_progress(job_id: UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(BookJob, job_id)
        if not job:
            return
        total, done, _pending = count_figure_progress(db, job.book_id)
        patch_job_checkpoint(
            db,
            job,
            figures_total=total,
            figures_done=done,
            stage_message=f"图片：{done} / {total} 张完成" if total else None,
        )
    finally:
        db.close()
