"""一键成书前置 Job：设定 → 文献 → 大纲 → 叙事宪法；章节写作由前端 SSE 批量生成。"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from app.agents.document_parser import DocumentParserAgent
from app.agents.literature_agent import LiteratureAgent
from app.agents.outline_agent import OutlineAgent
from app.database import SessionLocal
from app.llm.client import LLMClient
from app.llm.providers import (
    resolve_book_constitution_model,
    resolve_book_outline_model,
    resolve_book_writing_model,
)
from app.models.book import Book, BookStatus, CitationStyle
from app.models.book_job import BookJob, BookJobStatus, BookJobStep
from app.models.chapter import Chapter, ChapterStatus
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.routers.chapters import _ensure_narrative_constitution_thread
from app.services.auto_book_job_progress import patch_job_checkpoint
from app.services.citation_service import create_citation_from_paper
from app.services.literature_query_refiner import refine_literature_query
from app.services.preface_service import get_preface, set_preface
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


def _update_job(
    db,
    job: BookJob,
    *,
    step: BookJobStep | None = None,
    pct: int | None = None,
    status: BookJobStatus | None = None,
    error: str | None = None,
) -> None:
    if step is not None:
        job.current_step = step
    if pct is not None:
        job.progress_pct = pct
    if status is not None:
        job.status = status
        if status in (BookJobStatus.completed, BookJobStatus.failed, BookJobStatus.cancelled):
            job.finished_at = datetime.now(timezone.utc)
    if error is not None:
        job.error_message = error
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def _notify(db, user_id: UUID, title: str, body: str, payload: dict | None = None) -> None:
    db.add(
        Notification(
            user_id=user_id,
            type=NotificationType.book_job,
            title=title,
            body=body,
            payload_json=payload or {},
        )
    )
    db.commit()


def _infer_book_settings(book: Book, model: str) -> None:
    client = LLMClient()
    prompt = f"""根据书名与体裁推断书稿基础设定，输出 JSON：
{{"target_audience":"...", "topic_tags":["..."], "citation_style":"apa|gb_t7714|none", "topic_brief":"选题要点，非用户资料"}}
书名：{book.title}
类型：{book.book_type.value}
体裁：{book.style_type or ''}
学科：{book.discipline or ''}"""
    out = client.chat_completion(
        [{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": prompt}],
        model=model,
        max_tokens=1024,
        temperature=0.3,
    )
    data = parse_llm_json(out)
    if not book.target_audience:
        book.target_audience = str(data.get("target_audience") or "对相关主题感兴趣的读者")[:500]
    if not book.topic_tags:
        tags = data.get("topic_tags") or []
        book.topic_tags = [str(t)[:50] for t in tags][:8] if isinstance(tags, list) else []
    if not book.citation_style:
        cs = str(data.get("citation_style") or "apa").lower()
        if cs in ("none", "无", "无需"):
            book.citation_style = None
        elif cs == "gb_t7714":
            book.citation_style = CitationStyle.gb_t7714
        else:
            book.citation_style = CitationStyle.apa
    brief = str(data.get("topic_brief") or "").strip()
    if brief and not (book.topic_brief or "").strip():
        book.topic_brief = brief[:3000]
    import hashlib

    book.ai_inferred_settings = {
        "topic_brief": brief[:3000],
        "inferred_at": datetime.now(timezone.utc).isoformat(),
        "input_hash": hashlib.sha256(f"{book.title}|{book.book_type}|{book.style_type}".encode()).hexdigest(),
    }


def _maybe_apply_outline_title(book: Book, outline: dict) -> None:
    if not book.allow_title_optimization:
        return
    new_title = (outline.get("title") or "").strip()
    if new_title:
        book.title = new_title[:500]


def run_auto_book_job(job_id: UUID, *, worker_id: str | None = None) -> None:
    db = SessionLocal()
    try:
        job = db.get(BookJob, job_id)
        if not job or job.status not in (BookJobStatus.pending, BookJobStatus.running):
            return
        job.status = BookJobStatus.running
        db.commit()
        ck_fields: dict = {"stage_message": "正在初始化"}
        if worker_id:
            ck_fields["worker_id"] = worker_id
        else:
            ck_fields["worker_pid"] = os.getpid()
        patch_job_checkpoint(db, job, **ck_fields)

        book = db.get(Book, job.book_id)
        user = db.get(User, job.user_id)
        if not book or not user:
            _update_job(db, job, status=BookJobStatus.failed, error="书稿或用户不存在")
            return

        book.status = BookStatus.auto_generating
        db.commit()
        outline_model = resolve_book_outline_model(book, user)
        constitution_model = resolve_book_constitution_model(book, user)
        writing_model = resolve_book_writing_model(book, user)

        _update_job(db, job, step=BookJobStep.setting, pct=10)
        patch_job_checkpoint(db, job, stage_message="正在推断书稿设定")
        _infer_book_settings(book, writing_model)
        db.commit()

        _update_job(db, job, step=BookJobStep.literature, pct=25)
        patch_job_checkpoint(db, job, stage_message="正在规划参考文献")
        refined = refine_literature_query(db, book, raw_query=book.title)
        queries = refined.get("refined_queries") or [book.title]
        agent = LiteratureAgent()
        profile = book.style_type or "popular_science"
        tabbed = agent.search_tabbed(queries, profile, rows=15, raw_query=book.title)
        for paper in (tabbed.get("papers") or [])[:8]:
            try:
                create_citation_from_paper(db, book, paper)
            except Exception:
                pass
        db.commit()

        _update_job(db, job, step=BookJobStep.outline, pct=45)
        patch_job_checkpoint(db, job, stage_message="正在生成全书大纲")
        book.status = BookStatus.outline_generating
        db.commit()
        parser = DocumentParserAgent(db, book.id)
        snippets = parser.retrieve(book.title, top_k=5)
        from app.services.material_parse_service import get_book_level_writing_rules, get_primary_outline_for_book

        cfg = {
            "book_type": book.book_type.value,
            "style_type": book.style_type,
            "topic": book.title,
            "target_audience": book.target_audience or "大众读者",
            "target_words": book.target_words or 80000,
            "citation_style": book.citation_style.value if book.citation_style else "无需引用",
            "discipline": book.discipline,
            "topic_tags": list(book.topic_tags or []),
            "topic_brief": (book.topic_brief or "").strip() or None,
            "primary_outline": get_primary_outline_for_book(db, book.id),
            "writing_rules": get_book_level_writing_rules(db, book.id),
        }
        from app.services.writing.writing_context_builder import WritingContextBuilder

        wcb = WritingContextBuilder(db)
        snap = wcb.build_for_outline(book.id)
        cfg["writing_context"] = wcb.to_prompt_block(snap)
        outline = OutlineAgent().generate(cfg, snippets, model=outline_model)
        from app.services.material_parse_service import merge_outline_with_primary

        outline = merge_outline_with_primary(outline, cfg.get("primary_outline"))
        db.query(Chapter).filter(Chapter.book_id == book.id).delete()
        for ch in outline.get("chapters", []):
            meta = {
                "key_points": ch.get("key_points", []),
                "sections": ch.get("sections", []),
                "estimated_words": ch.get("estimated_words", 3000),
            }
            db.add(
                Chapter(
                    book_id=book.id,
                    index=ch["index"],
                    title=ch["title"],
                    summary=ch.get("summary"),
                    content=meta,
                    word_count=0,
                    status=ChapterStatus.pending,
                )
            )
        _maybe_apply_outline_title(book, outline)
        pf = get_preface(book)
        preface_brief = (outline.get("preface_brief") or "").strip()
        if preface_brief:
            pf["brief"] = preface_brief
            pf["status"] = "ready"
            set_preface(book, pf)
        n_chapters = len(outline.get("chapters") or [])
        patch_job_checkpoint(
            db,
            job,
            outline_ready=True,
            total_chapters=n_chapters,
            stage_message=f"大纲已生成，共 {n_chapters} 章",
        )
        db.commit()

        _update_job(db, job, step=BookJobStep.narrative, pct=75)
        patch_job_checkpoint(db, job, stage_message="正在准备写作规则")
        _ensure_narrative_constitution_thread(book.id, constitution_model)
        db.expire_all()
        book = db.get(Book, job.book_id)

        book.status = BookStatus.outline_ready
        db.commit()

        patch_job_checkpoint(
            db,
            job,
            narrative_ready=True,
            ready_for_editor=True,
            stage_message="写作规则已就绪，即将进入写作页",
        )
        _update_job(db, job, step=BookJobStep.done, pct=100, status=BookJobStatus.completed)
        _notify(
            db,
            user.id,
            "前置准备完成",
            f"《{book.title}》大纲与写作规则已就绪，将进入自动写作。",
            {"book_id": str(book.id), "job_id": str(job.id)},
        )
    except Exception as e:
        logger.exception("auto book job failed job=%s", job_id)
        job = db.get(BookJob, job_id)
        book = db.get(Book, job.book_id) if job else None
        if job:
            _update_job(db, job, status=BookJobStatus.failed, error=str(e)[:2000])
        if book and book.status == BookStatus.auto_generating:
            book.status = BookStatus.setup
            db.commit()
    finally:
        db.close()
