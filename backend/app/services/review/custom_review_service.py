"""Custom / ad-hoc review prompts."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.review_agent import ReviewAgent
from app.models.book import Book
from app.models.chapter import Chapter
from app.models.review_stage import BookReviewStageRun, ReviewStageStatus, ReviewTrack
from app.models.review_task import ReviewTask
from app.services.citation_service import is_bibliography_chapter
from app.services.review.review_finding_validator import enrich_finding_metadata, validate_finding
from app.services.review.review_agent_service import ReviewAgentService
from app.services.review_stage.review_finding_service import ReviewFindingService
from app.services.tiptap_convert import chapter_content_to_markdown
from app.services.writing.writing_context_builder import WritingContextBuilder
from app.routers.chapters import _chat_model_for_book


class CustomReviewService:
    def __init__(self, db: Session):
        self.db = db
        self.wcb = WritingContextBuilder(db)
        self.findings = ReviewFindingService(db)

    def run_custom(
        self,
        book: Book,
        *,
        prompt: str,
        chapter_index: int | None = None,
        user=None,
    ) -> dict:
        agent_svc = ReviewAgentService(self.db)
        task = agent_svc.build_task(
            book,
            scope="custom",
            chapter_index=chapter_index,
            custom_prompt=prompt,
            goal="custom",
        )
        return self.run_from_task(book, task, user=user)

    def run_from_task(self, book: Book, task: ReviewTask, *, user=None) -> dict:
        prompt = (task.custom_prompt or "").strip()
        if not prompt:
            raise ValueError("custom_prompt required")

        run = BookReviewStageRun(
            book_id=book.id,
            status=ReviewStageStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.flush()

        chapters = (
            self.db.query(Chapter)
            .filter(Chapter.book_id == book.id)
            .order_by(Chapter.index)
            .all()
        )
        if task.chapter_indexes:
            idx_set = set(task.chapter_indexes)
            chapters = [c for c in chapters if c.index in idx_set]
        chapters = [c for c in chapters if not is_bibliography_chapter(c)]

        from app.services.sources.stage_context_builder import StageContextBuilder

        review_query = " ".join(
            [book.title or "", prompt]
            + [f"{chapter.title or ''} {chapter.summary or ''}" for chapter in chapters[:20]]
        )
        stage_context = StageContextBuilder(self.db).build(
            book.id,
            stage="review",
            query=review_query,
            chapter_index=chapters[0].index if len(chapters) == 1 else None,
            top_k=20,
        )
        snap = stage_context["snapshot"]

        context_block = stage_context["prompt_block"][:7000]
        task_block = f"专项审校问题：{prompt}\n\n请只关注与上述问题相关的 findings，优先 goal_alignment 与 argument_quality 维度。"
        model = _chat_model_for_book(book, user, self.db) if user else "gpt-4o-mini"
        agent = ReviewAgent(model=model)
        items: list[dict] = []
        citation_style = book.citation_style.value if book.citation_style else "无"

        for ch in chapters[:5]:
            md = chapter_content_to_markdown(ch.content if isinstance(ch.content, dict) else None)
            if not md.strip():
                continue
            result = agent.review_chapter(
                chapter_title=ch.title or f"第{ch.index}章",
                body=md,
                book_title=book.title or "",
                book_type=book.book_type.value if book.book_type else "non_fiction",
                citation_style=citation_style,
                user_material=f"{context_block}\n\n{task_block}",
                narrative_constitution=(book.narrative_constitution or ""),
            )
            for issue in result.get("issues") or []:
                raw = {
                    "category": "custom_review",
                    "severity": issue.get("severity") or "medium",
                    "title": issue.get("title") or "专项审校发现",
                    "detail": issue.get("detail") or issue.get("explanation") or "",
                    "quote": issue.get("quote") or "",
                    "suggestion": issue.get("suggestion") or "",
                    "chapter_index": ch.index,
                    "dimension": issue.get("dimension"),
                    "issue_type": issue.get("issue_type"),
                }
                enriched = enrich_finding_metadata(raw, snap, chapter_md=md)
                validated = validate_finding(enriched)
                if validated:
                    items.append(validated)

        context_ref = {"task_id": str(task.id), "custom_prompt": prompt[:500]}
        if items:
            self.findings.persist_batch(
                run_id=run.id,
                book_id=book.id,
                track=ReviewTrack.writing_quality,
                items=items,
                source_ref=context_ref,
                context_snapshot=snap,
            )

        run.status = ReviewStageStatus.completed
        run.finished_at = datetime.now(timezone.utc)
        run.summary_json = {"custom_review": True, "finding_count": len(items)}
        self.db.flush()
        return {
            "run_id": str(run.id),
            "message": f"专项审校完成，发现 {len(items)} 条建议",
            "finding_count": len(items),
        }
