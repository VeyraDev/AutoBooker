"""Review agent orchestration — task sheet, objective checks, chapter agent, classification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.models.review_stage import BookReviewStageRun, ReviewStageStatus, ReviewTrack
from app.models.review_task import ReviewTask, ReviewTaskGoal, ReviewTaskScope, ReviewTaskStatus
from app.services.citation_service import is_bibliography_chapter
from app.services.review.format_column_reviewer import run_format_column_review
from app.services.review.objective_checks import run_objective_checks
from app.services.review.quality_reviewers import run_book_quality_review
from app.services.review.review_finding_validator import classify_product_dimension, enrich_finding_metadata
from app.services.review_stage.review_finding_service import ReviewFindingService
from app.services.review_stage.review_stage_service import ReviewStageService
from app.services.writing.writing_context_builder import WritingContextBuilder

DEFAULT_EXCLUSIONS = [
    "ai_dash_heuristic",
    "figure_caption_ai_tone",
    "single_punctuation_ai",
]


class ReviewAgentService:
    def __init__(self, db: Session):
        self.db = db
        self.wcb = WritingContextBuilder(db)
        self.findings = ReviewFindingService(db)

    def build_task(
        self,
        book: Book,
        *,
        scope: str = "book",
        chapter_index: int | None = None,
        custom_prompt: str | None = None,
        goal: str = "default",
    ) -> ReviewTask:
        snap = self.wcb.build_for_review(book.id)
        ctx_hash = self.wcb.context_hash(snap)
        chapter_indexes: list[int] | None = None
        task_scope = ReviewTaskScope(scope) if scope in {"book", "chapter", "custom"} else ReviewTaskScope.book
        task_goal = ReviewTaskGoal.custom if goal == "custom" or custom_prompt else ReviewTaskGoal.default

        if scope == "chapter" and chapter_index is not None:
            chapter_indexes = [chapter_index]
        elif scope == "custom" and chapter_index is not None:
            chapter_indexes = [chapter_index]

        adopted = {
            "public_rules": True,
            "editorial_principles": True,
            "user_writing_basis": bool(snap.get("must_avoid") or snap.get("must_keep")),
            "format_strategy": bool(
                isinstance(snap.get("format_strategy"), dict)
                and snap.get("format_strategy", {}).get("status") == "confirmed"
            ),
        }
        summary = self._render_summary_text(
            scope=scope,
            chapter_indexes=chapter_indexes,
            adopted=adopted,
            exclusions=DEFAULT_EXCLUSIONS,
            custom_prompt=custom_prompt,
            snap=snap,
        )
        task = ReviewTask(
            book_id=book.id,
            scope=task_scope,
            chapter_indexes=chapter_indexes,
            goal=task_goal,
            custom_prompt=(custom_prompt or "").strip() or None,
            adopted_standards=adopted,
            exclusions=list(DEFAULT_EXCLUSIONS),
            output_threshold="all_tiers",
            status=ReviewTaskStatus.pending,
            context_snapshot_hash=ctx_hash,
            summary_text=summary,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def run_task(self, book: Book, task: ReviewTask, *, user=None) -> dict:
        task.status = ReviewTaskStatus.running
        self.db.flush()
        try:
            if task.scope == ReviewTaskScope.chapter:
                idx = (task.chapter_indexes or [None])[0]
                result = self._run_chapter_scope(book, task, chapter_index=idx)
            elif task.scope == ReviewTaskScope.custom:
                from app.services.review.custom_review_service import CustomReviewService

                result = CustomReviewService(self.db).run_from_task(book, task, user=user)
            else:
                result = self._run_book_scope(book, task)
            task.status = ReviewTaskStatus.completed
            task.finished_at = datetime.now(timezone.utc)
            if result.get("run_id"):
                task.run_id = UUID(str(result["run_id"]))
            self.db.flush()
            return {
                "task_id": str(task.id),
                "run_id": result.get("run_id"),
                "status": "completed",
                "message": result.get("message", "审校完成"),
                "summary_text": task.summary_text,
            }
        except Exception as e:
            task.status = ReviewTaskStatus.failed
            task.error_message = str(e)[:500]
            task.finished_at = datetime.now(timezone.utc)
            self.db.flush()
            raise

    def _run_book_scope(self, book: Book, task: ReviewTask) -> dict:
        chapters = (
            self.db.query(Chapter)
            .filter(Chapter.book_id == book.id)
            .order_by(Chapter.index)
            .all()
        )
        chapters = [c for c in chapters if not is_bibliography_chapter(c)]
        from app.services.sources.stage_context_builder import StageContextBuilder

        review_query = " ".join(
            [book.title or ""]
            + [f"{chapter.title or ''} {chapter.summary or ''}" for chapter in chapters[:30]]
        )
        stage_context = StageContextBuilder(self.db).build(
            book.id,
            stage="review",
            query=review_query,
            top_k=20,
        )
        snap = stage_context["snapshot"]

        run = BookReviewStageRun(
            book_id=book.id,
            status=ReviewStageStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.flush()

        context_ref = {
            "context_hash": task.context_snapshot_hash,
            "task_id": str(task.id),
        }
        objective = run_objective_checks(
            self.db,
            book,
            chapters,
            context_snapshot=snap,
            context_excerpt=self.wcb.to_prompt_block(snap)[:2000],
        )
        objective = [enrich_finding_metadata(f, snap) for f in objective]
        self.findings.persist_batch(
            run_id=run.id,
            book_id=book.id,
            track=ReviewTrack.publication_standard,
            items=objective,
            source_ref=context_ref,
            context_snapshot=snap,
        )

        format_findings = run_format_column_review(chapters, snap)
        for f in format_findings:
            enrich_finding_metadata(f, snap)
        if format_findings:
            self.findings.persist_batch(
                run_id=run.id,
                book_id=book.id,
                track=ReviewTrack.publication_standard,
                items=format_findings,
                source_ref=context_ref,
                context_snapshot=snap,
            )

        quality_findings = run_book_quality_review(book, chapters, snap)
        if quality_findings:
            writing_quality_items = [
                f
                for f in quality_findings
                if str(f.get("product_dimension") or "") in {"argument_quality", "structure_progress", "goal_alignment", "language_credibility"}
            ]
            publication_items = [f for f in quality_findings if f not in writing_quality_items]
            if writing_quality_items:
                self.findings.persist_batch(
                    run_id=run.id,
                    book_id=book.id,
                    track=ReviewTrack.writing_quality,
                    items=writing_quality_items,
                    source_ref=context_ref,
                    context_snapshot=snap,
                )
            if publication_items:
                self.findings.persist_batch(
                    run_id=run.id,
                    book_id=book.id,
                    track=ReviewTrack.publication_standard,
                    items=publication_items,
                    source_ref=context_ref,
                    context_snapshot=snap,
                )

        wq = ReviewStageService(self.db).wq.aggregate(book.id)
        run.writing_quality_status = ReviewStageStatus(wq["status"])
        run.publication_standard_status = ReviewStageStatus.completed
        run.summary_json = {"writing_quality": wq, "task_id": str(task.id)}
        run.status = ReviewStageStatus.completed
        run.finished_at = datetime.now(timezone.utc)
        self.db.flush()
        return {"run_id": str(run.id), "message": "全书审校已完成"}

    def _run_chapter_scope(self, book: Book, task: ReviewTask, *, chapter_index: int | None) -> dict:
        if chapter_index is None:
            raise ValueError("chapter_index required")
        ch = (
            self.db.query(Chapter)
            .filter(Chapter.book_id == book.id, Chapter.index == chapter_index)
            .first()
        )
        if not ch or is_bibliography_chapter(ch):
            raise ValueError("Chapter not found")
        from app.routers.review import _create_review_report, _chapter_markdown

        md = _chapter_markdown(ch)
        if not md.strip():
            raise ValueError("Chapter has no content")
        task_block = task.summary_text or ""
        _create_review_report(book, ch, md, self.db, review_context_block=task_block)
        return {"run_id": None, "message": f"第{chapter_index}章审校完成"}

    def get_task(self, book_id: UUID, task_id: UUID) -> ReviewTask | None:
        return (
            self.db.query(ReviewTask)
            .filter(ReviewTask.id == task_id, ReviewTask.book_id == book_id)
            .first()
        )

    def latest_task(self, book_id: UUID) -> ReviewTask | None:
        return (
            self.db.query(ReviewTask)
            .filter(ReviewTask.book_id == book_id)
            .order_by(ReviewTask.created_at.desc())
            .first()
        )

    @staticmethod
    def classify_findings(items: list[dict]) -> list[dict]:
        out: list[dict] = []
        for raw in items:
            item = dict(raw)
            item["product_dimension"] = classify_product_dimension(item)
            out.append(item)
        return out

    @staticmethod
    def _render_summary_text(
        *,
        scope: str,
        chapter_indexes: list[int] | None,
        adopted: dict,
        exclusions: list[str],
        custom_prompt: str | None,
        snap: dict,
    ) -> str:
        lines = ["本次审校任务单", ""]
        if scope == "chapter" and chapter_indexes:
            lines.append(f"审校范围：第 {chapter_indexes[0]} 章")
        elif scope == "custom":
            lines.append(f"审校范围：专项（第 {chapter_indexes[0]} 章）" if chapter_indexes else "审校范围：全书专项")
        else:
            lines.append("审校范围：全书")
        lines.append("")
        lines.append("采用标准：")
        if adopted.get("public_rules"):
            lines.append("- 公开出版规则")
        if adopted.get("editorial_principles"):
            lines.append("- AutoBooker 内置编辑原则")
        if adopted.get("user_writing_basis"):
            for item in (snap.get("must_avoid") or [])[:3]:
                lines.append(f"- 用户要求（避免）：{str(item)[:80]}")
        if adopted.get("format_strategy"):
            lines.append("- 全书体例与栏目策略")
        lines.append("")
        lines.append("本次排除：")
        lines.append("- 不把图题/表题标为 AI 味")
        lines.append("- 不把单个破折号/标点当 AI 味")
        if custom_prompt:
            lines.append("")
            lines.append(f"专项问题：{custom_prompt.strip()[:300]}")
        return "\n".join(lines)
