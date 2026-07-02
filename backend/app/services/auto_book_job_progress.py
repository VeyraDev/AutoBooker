"""一键成书 Job 进度 checkpoint 读写。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.book_job import BookJob
from app.models.chapter import Chapter, ChapterStatus
from app.models.figure import Figure, FigureStatus, FigureType


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def patch_job_checkpoint(db: Session, job: BookJob, **fields) -> dict:
    ck = dict(job.checkpoint_json or {})
    ck.update({k: v for k, v in fields.items() if v is not None})
    ck["updated_at"] = _now_iso()
    if "started_at" not in ck:
        ck["started_at"] = _now_iso()
    job.checkpoint_json = ck
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ck


def count_figure_progress(db: Session, book_id: UUID) -> tuple[int, int, int]:
    q = db.query(Figure).filter(
        Figure.book_id == book_id,
        Figure.figure_type != FigureType.screenshot,
    )
    total = int(q.count())
    done = int(
        q.filter(
            Figure.status.in_(
                (FigureStatus.generated, FigureStatus.uploaded, FigureStatus.approved)
            )
        ).count()
    )
    pending = max(0, total - done)
    return total, done, pending


def build_job_detail(db: Session, job: BookJob) -> dict:
    ck = dict(job.checkpoint_json or {})
    book = db.get(Book, job.book_id)
    chapter_count = int(
        db.query(func.count(Chapter.id)).filter(Chapter.book_id == job.book_id).scalar() or 0
    )
    chapters_done = int(
        db.query(func.count(Chapter.id))
        .filter(Chapter.book_id == job.book_id, Chapter.status == ChapterStatus.done)
        .scalar()
        or 0
    )
    fig_total, fig_done, fig_pending = count_figure_progress(db, job.book_id)
    started_at = ck.get("started_at")
    elapsed_seconds = 0
    if started_at:
        try:
            started = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
            elapsed_seconds = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
        except ValueError:
            elapsed_seconds = 0

    return {
        "book_title": (book.title if book else "") or "",
        "outline_ready": bool(ck.get("outline_ready")),
        "narrative_ready": bool(ck.get("narrative_ready")),
        "writing_started": bool(ck.get("writing_started")),
        "ready_for_editor": bool(ck.get("ready_for_editor")),
        "total_chapters": int(ck.get("total_chapters") or chapter_count),
        "chapters_done": int(ck.get("chapters_done") or chapters_done),
        "current_chapter_index": ck.get("current_chapter_index"),
        "figures_total": int(ck.get("figures_total") or fig_total),
        "figures_done": int(ck.get("figures_done") or fig_done),
        "figures_pending": fig_pending,
        "stage_message": str(ck.get("stage_message") or ""),
        "started_at": started_at,
        "elapsed_seconds": elapsed_seconds,
        "updated_at": ck.get("updated_at"),
    }
