"""Unified review workspace — adapter over chapter + book findings."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.models.chapter_review import ChapterReviewIssue, ReviewApplication
from app.models.review_stage import BookReviewFinding, BookReviewStageRun, ReviewFindingStatus, ReviewStageStatus
from app.models.review_task import ReviewTask
from app.services.citation_service import is_bibliography_chapter
from app.services.review.review_agent_service import ReviewAgentService
from app.services.review.review_finding_validator import severity_to_tier
from app.services.review.review_preference_memory import record_review_preference
from app.services.review.review_rule_library import match_basis_refs
from app.services.review_stage.review_finding_service import ReviewFindingService
from app.services.writing.writing_context_builder import WritingContextBuilder


def _chapter_issue_status(issue: ChapterReviewIssue) -> str:
    st = (issue.status or "open").strip().lower()
    if st == "open" and issue.applied_at and not issue.resolved_at:
        return "applied_pending_recheck"
    return st


def _book_finding_status(row: BookReviewFinding) -> str:
    return row.status.value if hasattr(row.status, "value") else str(row.status)


def _issue_meta(issue: ChapterReviewIssue) -> dict:
    ev = issue.quality_evidence if isinstance(issue.quality_evidence, dict) else {}
    return ev


def _batch_preview_skip_reason(issue: ChapterReviewIssue) -> str | None:
    if _chapter_issue_status(issue) != "open":
        return "not_open"
    meta = _issue_meta(issue)
    if meta.get("fix_capability") != "preview_apply":
        return "not_preview_apply"
    if not (
        issue.char_start is not None
        or issue.paragraph_id
        or issue.paragraph_index is not None
        or (issue.quote or "").strip()
    ):
        return "not_locatable"
    return None


def _book_meta(row: BookReviewFinding) -> dict:
    ref = row.source_ref_json if isinstance(row.source_ref_json, dict) else {}
    return ref


def _evidence_items_from_meta(meta: dict, basis_refs: list[str]) -> list[dict]:
    items: list[dict] = []
    title_benchmark = meta.get("title_benchmark") if isinstance(meta, dict) else None
    if isinstance(title_benchmark, dict):
        sample_count = _safe_int(title_benchmark.get("sample_count"))
        soft_min = _safe_int(title_benchmark.get("soft_min"))
        soft_max = _safe_int(title_benchmark.get("soft_max"))
        median_len = _safe_int(title_benchmark.get("median_len"))
        source = str(title_benchmark.get("source") or "fallback")
        examples = [str(x) for x in (title_benchmark.get("examples") or []) if str(x).strip()][:5]
        if sample_count > 0 and soft_min > 0 and soft_max > 0:
            detail = (
                f"参考 {source} 中 {sample_count} 个可识别标题，常见区间约 "
                f"{soft_min}-{soft_max} 个中文字符"
                + (f"，中位数约 {median_len}。" if median_len > 0 else "。")
            )
        else:
            detail = "当前采用书类兜底标题长度规则，建议人工结合定位判断。"
        items.append(
            {
                "type": "title_benchmark",
                "label": "标题样本基准",
                "detail": detail,
                "source": source,
                "examples": examples,
            }
        )
    evidence = meta.get("evidence") if isinstance(meta, dict) else None
    if isinstance(evidence, list):
        for idx, item in enumerate(evidence[:5], start=1):
            text = str(item).strip()
            if not text:
                continue
            items.append(
                {
                    "type": "review_evidence",
                    "label": f"审校证据 {idx}",
                    "detail": text[:500],
                    "source": "review_output",
                    "examples": [],
                }
            )
    verification_status = str(meta.get("verification_status") or "").strip() if isinstance(meta, dict) else ""
    if verification_status:
        items.append(
            {
                "type": "verification_status",
                "label": "核验状态",
                "detail": verification_status,
                "source": "verification",
                "examples": [],
            }
        )
    if not items and basis_refs:
        items.append(
            {
                "type": "basis_refs",
                "label": "规则依据",
                "detail": "已匹配到结构化依据来源，见上方依据列表。",
                "source": "basis_refs",
                "examples": basis_refs[:5],
            }
        )
    return items


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class ReviewWorkspaceService:
    def __init__(self, db: Session):
        self.db = db

    def _context_snapshot(self, book_id: UUID) -> dict:
        wcb = WritingContextBuilder(self.db)
        return wcb.build_snapshot(book_id)

    def _chapter_map(self, book_id: UUID) -> dict[UUID, Chapter]:
        rows = self.db.query(Chapter).filter(Chapter.book_id == book_id).all()
        return {r.id: r for r in rows}

    def _task_out(self, task: ReviewTask | None) -> dict | None:
        if not task:
            return None
        return {
            "id": task.id,
            "book_id": task.book_id,
            "scope": task.scope.value if hasattr(task.scope, "value") else str(task.scope),
            "chapter_indexes": task.chapter_indexes,
            "goal": task.goal.value if hasattr(task.goal, "value") else str(task.goal),
            "custom_prompt": task.custom_prompt,
            "adopted_standards": task.adopted_standards or {},
            "exclusions": task.exclusions or [],
            "status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "summary_text": task.summary_text,
            "run_id": str(task.run_id) if task.run_id else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
        }

    def _chapter_issue_to_dto(self, issue: ChapterReviewIssue, chapters: dict[UUID, Chapter], snap: dict) -> dict:
        ch = chapters.get(issue.chapter_id)
        meta = _issue_meta(issue)
        finding = {
            "title": issue.title,
            "detail": issue.explanation,
            "quote": issue.quote,
            "category": issue.issue_type,
            "detector": issue.detector,
            "dimension": issue.dimension,
            "severity": issue.severity,
        }
        basis = list(meta.get("basis_refs") or []) or match_basis_refs(finding, snap)
        return {
            "id": issue.id,
            "source": "chapter",
            "chapter_index": ch.index if ch else None,
            "chapter_title": ch.title if ch else None,
            "tier": severity_to_tier(
                issue.severity,
                verification_status=(meta.get("verification_status") if isinstance(meta, dict) else None),
            ),
            "status": _chapter_issue_status(issue),
            "title": issue.title or "",
            "detail": issue.explanation or "",
            "quote": issue.quote or None,
            "suggestion": issue.replacement_text or None,
            "basis_refs": basis,
            "evidence_items": _evidence_items_from_meta(meta, basis),
            "paragraph_id": issue.paragraph_id,
            "paragraph_index": issue.paragraph_index,
            "char_start": issue.char_start,
            "char_end": issue.char_end,
            "category": issue.issue_type,
            "track": None,
            "detector": issue.detector,
            "dimension": issue.dimension,
            "issue_type": issue.issue_type,
            "product_dimension": meta.get("product_dimension"),
            "impact_scope": meta.get("impact_scope"),
            "locatable": bool(meta.get("locatable", issue.char_start is not None)),
            "task_id": meta.get("task_id"),
            "validation_passed": meta.get("validation_passed", True),
            "filter_reason": meta.get("filter_reason"),
            "why_it_matters": meta.get("why_it_matters") or None,
            "verification_status": meta.get("verification_status"),
            "action_options": meta.get("action_options") or [],
            "fix_capability": meta.get("fix_capability"),
            "prefer_evidence_binding": bool(meta.get("prefer_evidence_binding")),
        }

    def _book_finding_to_dto(self, row: BookReviewFinding, snap: dict) -> dict:
        ref = _book_meta(row)
        basis = list(ref.get("basis_refs") or [])
        if not basis:
            basis = match_basis_refs(
                {"category": row.category, "detail": row.detail, "title": row.title},
                snap,
            )
        return {
            "id": row.id,
            "source": "book",
            "chapter_index": ref.get("chapter_index"),
            "chapter_title": None,
            "tier": severity_to_tier(
                row.severity,
                verification_status=ref.get("verification_status"),
            ),
            "status": _book_finding_status(row),
            "title": row.title or "",
            "detail": row.detail or "",
            "quote": ref.get("quote"),
            "suggestion": row.suggestion or None,
            "basis_refs": basis,
            "evidence_items": _evidence_items_from_meta(ref, basis),
            "paragraph_id": ref.get("paragraph_id"),
            "paragraph_index": ref.get("paragraph_index"),
            "char_start": ref.get("char_start"),
            "char_end": ref.get("char_end"),
            "category": row.category,
            "track": row.track.value if hasattr(row.track, "value") else str(row.track),
            "detector": None,
            "dimension": None,
            "issue_type": row.category,
            "product_dimension": ref.get("product_dimension"),
            "impact_scope": ref.get("impact_scope") or "book",
            "locatable": bool(ref.get("locatable", False)),
            "task_id": ref.get("task_id"),
            "validation_passed": ref.get("validation_passed", True),
            "filter_reason": ref.get("filter_reason"),
            "why_it_matters": ref.get("why_it_matters") or None,
            "verification_status": ref.get("verification_status"),
            "action_options": ref.get("action_options") or [],
            "fix_capability": ref.get("fix_capability"),
            "prefer_evidence_binding": bool(ref.get("prefer_evidence_binding")),
        }

    def list_findings(
        self,
        book_id: UUID,
        *,
        tier: str | None = None,
        chapter_index: int | None = None,
        status: str | None = None,
        product_dimension: str | None = None,
    ) -> list[dict]:
        snap = self._context_snapshot(book_id)
        chapters = self._chapter_map(book_id)
        chapter_ids = [c.id for c in chapters.values() if chapter_index is None or c.index == chapter_index]

        chapter_issues = (
            self.db.query(ChapterReviewIssue)
            .filter(ChapterReviewIssue.chapter_id.in_(chapter_ids) if chapter_ids else False)
            .order_by(ChapterReviewIssue.created_at.desc())
            .all()
            if chapter_ids
            else []
        )

        book_findings = (
            self.db.query(BookReviewFinding)
            .filter(BookReviewFinding.book_id == book_id)
            .order_by(BookReviewFinding.created_at.desc())
            .all()
        )

        rows: list[dict] = []
        for issue in chapter_issues:
            rows.append(self._chapter_issue_to_dto(issue, chapters, snap))
        for bf in book_findings:
            if chapter_index is not None and bf.source_ref_json:
                ref_idx = (bf.source_ref_json or {}).get("chapter_index")
                if ref_idx is not None and ref_idx != chapter_index:
                    continue
            rows.append(self._book_finding_to_dto(bf, snap))

        if tier:
            rows = [r for r in rows if r["tier"] == tier]
        if product_dimension:
            rows = [r for r in rows if r.get("product_dimension") == product_dimension]
        if status:
            rows = [
                r
                for r in rows
                if r["status"] == status
                or (status == "open" and r["status"] in {"open", "applied_pending_recheck"})
            ]
        elif not status:
            rows = [r for r in rows if r["status"] not in {"resolved", "dismissed"}]
        return rows

    def summary(self, book_id: UUID) -> dict:
        findings = self.list_findings(book_id)
        must_fix = sum(1 for f in findings if f["tier"] == "must_fix")
        suggest = sum(1 for f in findings if f["tier"] == "suggest")
        observe = sum(1 for f in findings if f["tier"] == "observe")
        needs_verification = sum(1 for f in findings if f["tier"] == "needs_verification")
        by_chapter: dict[str, int] = {}
        for f in findings:
            if f["tier"] != "must_fix":
                continue
            key = str(f["chapter_index"] or "book")
            by_chapter[key] = by_chapter.get(key, 0) + 1

        run = (
            self.db.query(BookReviewStageRun)
            .filter(BookReviewStageRun.book_id == book_id)
            .order_by(BookReviewStageRun.created_at.desc())
            .first()
        )
        run_status = run.status.value if run and hasattr(run.status, "value") else None
        latest_task = ReviewAgentService(self.db).latest_task(book_id)
        return {
            "book_id": book_id,
            "must_fix_count": must_fix,
            "suggest_count": suggest,
            "observe_count": observe,
            "needs_verification_count": needs_verification,
            "open_count": len(findings),
            "run_status": run_status,
            "by_chapter": by_chapter,
            "latest_task": self._task_out(latest_task),
        }

    def get_task(self, book_id: UUID, task_id: UUID) -> dict | None:
        task = ReviewAgentService(self.db).get_task(book_id, task_id)
        return self._task_out(task)

    def run_review(self, book: Book, *, scope: str = "book", chapter_index: int | None = None, user=None) -> dict:
        agent = ReviewAgentService(self.db)
        task = agent.build_task(book, scope=scope, chapter_index=chapter_index)
        return agent.run_task(book, task, user=user)

    def run_custom(self, book: Book, *, prompt: str, chapter_index: int | None = None, user=None) -> dict:
        from app.services.review.custom_review_service import CustomReviewService

        agent = ReviewAgentService(self.db)
        task = agent.build_task(
            book,
            scope="custom",
            chapter_index=chapter_index,
            custom_prompt=prompt,
            goal="custom",
        )
        result = CustomReviewService(self.db).run_from_task(book, task, user=user)
        from app.models.review_task import ReviewTaskStatus
        from datetime import datetime, timezone
        from uuid import UUID as _UUID

        task.status = ReviewTaskStatus.completed
        task.finished_at = datetime.now(timezone.utc)
        if result.get("run_id"):
            task.run_id = _UUID(str(result["run_id"]))
        self.db.flush()
        return {
            "task_id": str(task.id),
            "run_id": result.get("run_id"),
            "status": "completed",
            "message": result.get("message", "专项审校完成"),
            "summary_text": task.summary_text,
        }

    def patch_finding(self, book_id: UUID, finding_id: UUID, source: str, status: str) -> dict | None:
        if source == "book":
            mapped = {
                "resolved": ReviewFindingStatus.resolved,
                "dismissed": ReviewFindingStatus.dismissed,
                "open": ReviewFindingStatus.open,
            }.get(status)
            if not mapped:
                raise ValueError("Invalid status")
            row = ReviewFindingService(self.db).update_status(finding_id, book_id, mapped)
            if not row:
                return None
            if status in {"dismissed", "resolved"}:
                ref = _book_meta(row)
                track_value = row.track.value if hasattr(row.track, "value") else row.track
                record_review_preference(
                    self.db,
                    book_id,
                    decision="dismissed" if status == "dismissed" else "accepted",
                    product_dimension=ref.get("product_dimension") or track_value,
                    issue_type=row.category,
                    fix_capability=ref.get("fix_capability"),
                )
            snap = self._context_snapshot(book_id)
            return self._book_finding_to_dto(row, snap)

        issue = self.db.get(ChapterReviewIssue, finding_id)
        if not issue:
            return None
        ch = self.db.get(Chapter, issue.chapter_id)
        if not ch or ch.book_id != book_id:
            return None
        if status not in {"open", "resolved", "dismissed", "applied_pending_recheck"}:
            raise ValueError("Invalid status")
        if status == "applied_pending_recheck":
            issue.status = "open"
        else:
            issue.status = status
            if status == "resolved":
                from datetime import datetime, timezone

                issue.resolved_at = datetime.now(timezone.utc)
            if status in {"dismissed", "resolved"}:
                meta = _issue_meta(issue)
                record_review_preference(
                    self.db,
                    book_id,
                    decision="dismissed" if status == "dismissed" else "accepted",
                    product_dimension=meta.get("product_dimension") or issue.dimension,
                    issue_type=issue.issue_type,
                    fix_capability=meta.get("fix_capability"),
                )
        self.db.flush()
        snap = self._context_snapshot(book_id)
        chapters = self._chapter_map(book_id)
        return self._chapter_issue_to_dto(issue, chapters, snap)

    def recheck_finding(self, book_id: UUID, finding_id: UUID) -> dict:
        from datetime import datetime, timezone

        issue = self.db.get(ChapterReviewIssue, finding_id)
        if not issue:
            raise ValueError("Finding not found")
        ch = self.db.get(Chapter, issue.chapter_id)
        if not ch or ch.book_id != book_id:
            raise ValueError("Finding not found")
        st = _chapter_issue_status(issue)
        if st != "applied_pending_recheck":
            raise ValueError("Issue is not pending recheck")

        from app.services.tiptap_convert import chapter_content_to_markdown

        md = chapter_content_to_markdown(ch.content if isinstance(ch.content, dict) else None)
        quote = (issue.quote or "").strip()
        still_present = bool(quote and quote in md)
        if still_present:
            issue.status = "open"
            issue.applied_at = None
            message = "复查未通过，问题仍存在"
        else:
            issue.status = "resolved"
            issue.resolved_at = datetime.now(timezone.utc)
            message = "复查通过，已标记为已处理"
        self.db.flush()
        snap = self._context_snapshot(book_id)
        chapters = self._chapter_map(book_id)
        dto = self._chapter_issue_to_dto(issue, chapters, snap)
        dto["recheck_message"] = message
        return dto

    def finding_history(self, book_id: UUID, finding_id: UUID) -> list[dict]:
        issue = self.db.get(ChapterReviewIssue, finding_id)
        if not issue:
            return []
        ch = self.db.get(Chapter, issue.chapter_id)
        if not ch or ch.book_id != book_id:
            return []
        apps = (
            self.db.query(ReviewApplication)
            .filter(ReviewApplication.issue_id == finding_id)
            .order_by(ReviewApplication.created_at.desc())
            .all()
        )
        return [
            {
                "application_id": str(a.id),
                "apply_type": a.apply_type,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "locator_strategy": a.locator_strategy or "",
                "locator_confidence": float(a.locator_confidence or 0),
            }
            for a in apps
        ]

    def _preview_figure_table_fix(
        self,
        book: Book,
        ch: Chapter,
        review,
        issue: ChapterReviewIssue,
        current_md: str,
    ) -> dict:
        from app.repositories import review_repository
        from app.services.chapter_figure_table_normalize import normalize_chapter_figures_tables
        from app.services.review_apply import preview_full_chapter_application
        from app.services.review_incremental import affected_dimensions

        content = ch.content if isinstance(ch.content, dict) else {}
        tiptap = content.get("tiptap_json") if isinstance(content, dict) else None
        if not isinstance(tiptap, dict):
            raise ValueError("章节无 TipTap 内容可排序，请先保存章节正文后重试")

        result = normalize_chapter_figures_tables(
            book.id,
            ch.index,
            tiptap,
            self.db,
            book=book,
            persist=False,
        )
        preview = preview_full_chapter_application(
            current_markdown=current_md,
            issue_snapshot_hash=issue.snapshot_hash,
            result_markdown=str(result.get("text") or ""),
            apply_type="figure_table_normalize",
            result_tiptap_json=result.get("tiptap_json") if isinstance(result.get("tiptap_json"), dict) else None,
        )
        diff = preview["diff"]
        affected = affected_dimensions(issue.issue_type, issue.dimension)
        app = review_repository.create_application(
            self.db,
            issue=issue,
            review=review,
            chapter_id=ch.id,
            before_hash=preview["before_hash"],
            after_hash=preview["after_hash"],
            apply_type="figure_table_normalize",
            locator_strategy=preview["locator_strategy"],
            locator_confidence=preview["locator_confidence"],
            diff=diff,
            affected_dimensions=affected,
            score_before={"total_score": review.total_score, "dimensions": review.dimensions},
            warning={"overview": result.get("overview") or []},
        )
        self.db.flush()
        return {
            "issue_id": str(issue.id),
            "application_id": str(app.id),
            "quote": preview["quote"] or issue.quote or "",
            "result_text": str(diff.get("after") or ""),
            "result_markdown": preview["result_markdown"],
            "preview_kind": "replace",
            "preview_required": True,
            "stale": preview["stale"],
            "locator_strategy": preview["locator_strategy"],
            "locator_confidence": preview["locator_confidence"],
            "char_start": diff.get("char_start"),
            "char_end": diff.get("char_end"),
            "paragraph_index": issue.paragraph_index,
            "paragraph_id": issue.paragraph_id,
        }

    def _preview_first_line_indent_fix(
        self,
        book: Book,
        ch: Chapter,
        review,
        issue: ChapterReviewIssue,
        current_md: str,
    ) -> dict:
        from app.repositories import review_repository
        from app.services.markdown_to_tiptap import markdown_body_to_tiptap_blocks
        from app.services.review.layout_autofix import normalize_first_line_indent
        from app.services.review_apply import preview_full_chapter_application
        from app.services.review_incremental import affected_dimensions

        content = ch.content if isinstance(ch.content, dict) else {}
        tiptap = content.get("tiptap_json") if isinstance(content, dict) else None
        if not isinstance(tiptap, dict) or tiptap.get("type") != "doc":
            tiptap = {"type": "doc", "content": markdown_body_to_tiptap_blocks(current_md)}
        result = normalize_first_line_indent(current_md, tiptap)
        if int(result.get("changed_count") or 0) <= 0:
            raise ValueError("未检测到可应用的首行缩进修改")
        preview = preview_full_chapter_application(
            current_markdown=current_md,
            issue_snapshot_hash=issue.snapshot_hash,
            result_markdown=str(result.get("text") or ""),
            apply_type="first_line_indent",
            result_tiptap_json=result.get("tiptap_json") if isinstance(result.get("tiptap_json"), dict) else None,
        )
        affected = affected_dimensions(issue.issue_type, issue.dimension)
        app = review_repository.create_application(
            self.db,
            issue=issue,
            review=review,
            chapter_id=ch.id,
            before_hash=preview["before_hash"],
            after_hash=preview["after_hash"],
            apply_type="first_line_indent",
            locator_strategy=preview["locator_strategy"],
            locator_confidence=preview["locator_confidence"],
            diff=preview["diff"],
            affected_dimensions=affected,
            score_before={"total_score": review.total_score, "dimensions": review.dimensions},
            warning={"changed_count": int(result.get("changed_count") or 0)},
        )
        self.db.flush()
        return {
            "issue_id": str(issue.id),
            "application_id": str(app.id),
            "quote": preview["quote"] or issue.quote or "",
            "result_text": preview["result_text"],
            "result_markdown": preview["result_markdown"],
            "preview_kind": "replace",
            "preview_required": True,
            "stale": preview["stale"],
            "locator_strategy": preview["locator_strategy"],
            "locator_confidence": preview["locator_confidence"],
            "char_start": preview["char_start"],
            "char_end": preview["char_end"],
            "paragraph_index": issue.paragraph_index,
            "paragraph_id": issue.paragraph_id,
        }

    def apply_finding(
        self,
        book: Book,
        finding_id: UUID,
        *,
        chat_model: str,
        replacement_text: str | None = None,
        action_type: str | None = None,
        action_option_id: str | None = None,
    ) -> dict:
        from app.models.chapter_review import ChapterReview
        from app.repositories import review_repository
        from app.services.review.data_evidence_policy import (
            DATA_ACTION_OPTIONS,
            is_data_evidence_issue,
        )
        from app.services.review_apply import apply_review_issue_text, preview_issue_application
        from app.services.review_incremental import affected_dimensions
        from app.services.tiptap_convert import chapter_content_to_markdown

        issue = self.db.get(ChapterReviewIssue, finding_id)
        if not issue:
            raise ValueError("Finding not found")
        ch = self.db.get(Chapter, issue.chapter_id)
        if not ch or ch.book_id != book.id:
            raise ValueError("Finding not found")
        review = self.db.get(ChapterReview, issue.review_id)
        if not review:
            raise ValueError("Review not found")

        content = ch.content if isinstance(ch.content, dict) else None
        current_md = chapter_content_to_markdown(content)
        meta = issue.quality_evidence if isinstance(issue.quality_evidence, dict) else {}
        fix_capability = str(meta.get("fix_capability") or "").strip()
        if fix_capability in {"manual_only", "observe_only"}:
            raise ValueError("该问题不支持自动生成修改预览，请人工处理或仅作观察")
        if fix_capability == "choice_then_apply" and not (action_option_id or (replacement_text or "").strip()):
            raise ValueError("该问题需要先选择处理方式，再生成修改预览")
        if issue.issue_type == "figure_table_numbering":
            return self._preview_figure_table_fix(book, ch, review, issue, current_md)
        if issue.issue_type == "first_line_indent":
            return self._preview_first_line_indent_fix(book, ch, review, issue, current_md)
        finding_probe = {
            "issue_type": issue.issue_type,
            "dimension": issue.dimension,
            "title": issue.title,
            "detail": issue.explanation,
            "quote": issue.quote,
            "product_dimension": meta.get("product_dimension"),
        }

        option_instruction = None
        act = (action_type or issue.action or "replace").strip().lower()
        if action_option_id:
            options = meta.get("action_options") or DATA_ACTION_OPTIONS
            chosen = next((o for o in options if str(o.get("id")) == action_option_id), None)
            if not chosen:
                chosen = next((o for o in DATA_ACTION_OPTIONS if o["id"] == action_option_id), None)
            if not chosen:
                raise ValueError(f"未知处理方式：{action_option_id}")
            if action_option_id == "add_source":
                raise ValueError("请先在文献搜索中绑定来源，或手动插入（来源：机构，年份）标注后再应用")
            act = str(chosen.get("action_type") or "revise")
            option_instruction = str(chosen.get("instruction") or chosen.get("description") or "")

        preview_kind = "replace"
        if replacement_text is not None and replacement_text.strip():
            replacement = replacement_text.strip()
        elif act == "delete":
            replacement = ""
            preview_kind = "delete"
        elif act == "replace" and (issue.replacement_text or "").strip():
            replacement = issue.replacement_text.strip()
        elif is_data_evidence_issue(finding_probe) and not option_instruction and act in {"revise", "choose", ""}:
            raise ValueError(
                "数据/事实类问题请先选择处理方式：补充来源、保留为估算、或删除精确比例；"
                "系统不会自动改成空泛比例表述。"
            )
        else:
            replacement, preview_kind = apply_review_issue_text(
                book=book,
                chat_model=chat_model,
                action_type=act if act != "choose" else "revise",
                quote=issue.quote or "",
                suggestion=option_instruction or issue.replacement_text or "",
                detail=issue.explanation or "",
                context=current_md[:12000],
                forbid_vague_ratio_rewrite=is_data_evidence_issue(finding_probe),
            )

        preview = preview_issue_application(
            current_markdown=current_md,
            issue_snapshot_hash=issue.snapshot_hash,
            quote=issue.quote or "",
            action_type=act,
            replacement_text=replacement,
            paragraph_id=issue.paragraph_id,
            paragraph_index=issue.paragraph_index,
            char_start=issue.char_start,
            char_end=issue.char_end,
        )
        affected = affected_dimensions(issue.issue_type, issue.dimension)
        app = review_repository.create_application(
            self.db,
            issue=issue,
            review=review,
            chapter_id=ch.id,
            before_hash=preview["before_hash"],
            after_hash=preview["after_hash"],
            apply_type=act,
            locator_strategy=preview["locator_strategy"],
            locator_confidence=preview["locator_confidence"],
            diff=preview["diff"],
            affected_dimensions=affected,
            score_before={"total_score": review.total_score, "dimensions": review.dimensions},
        )
        self.db.flush()
        return {
            "issue_id": str(issue.id),
            "application_id": str(app.id),
            "quote": preview.get("quote") or issue.quote or "",
            "result_text": preview["result_text"],
            "result_markdown": preview["result_markdown"],
            "preview_kind": preview_kind if preview_kind in {"replace", "insert", "delete"} else preview["preview_kind"],
            "preview_required": preview["preview_required"],
            "stale": preview["stale"],
            "locator_strategy": preview["locator_strategy"],
            "locator_confidence": preview["locator_confidence"],
            "char_start": preview["char_start"],
            "char_end": preview["char_end"],
            "paragraph_index": preview["paragraph_index"],
            "paragraph_id": preview["paragraph_id"],
        }

    def batch_preview_findings(
        self,
        book: Book,
        finding_ids: list[UUID],
        *,
        chat_model: str,
        limit: int = 10,
    ) -> dict:
        requested = list(dict.fromkeys(finding_ids))
        capped = max(1, min(int(limit or 10), 20))
        items: list[dict] = []
        skipped: list[dict] = []

        for idx, finding_id in enumerate(requested):
            if idx >= capped:
                skipped.append({"finding_id": finding_id, "reason": "over_limit", "title": None})
                continue
            issue = self.db.get(ChapterReviewIssue, finding_id)
            if not issue:
                skipped.append({"finding_id": finding_id, "reason": "not_found", "title": None})
                continue
            ch = self.db.get(Chapter, issue.chapter_id)
            if not ch or ch.book_id != book.id:
                skipped.append({"finding_id": finding_id, "reason": "not_found", "title": issue.title})
                continue
            reason = _batch_preview_skip_reason(issue)
            if reason:
                skipped.append({"finding_id": finding_id, "reason": reason, "title": issue.title})
                continue
            try:
                items.append(
                    self.apply_finding(
                        book,
                        finding_id,
                        chat_model=chat_model,
                    )
                )
            except ValueError as exc:
                skipped.append({"finding_id": finding_id, "reason": str(exc), "title": issue.title})

        return {
            "requested_count": len(requested),
            "previewed_count": len(items),
            "skipped_count": len(skipped),
            "items": items,
            "skipped": skipped,
        }
