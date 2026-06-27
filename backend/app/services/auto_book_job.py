"""一键生成书稿 Job 执行器。"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import func

from app.agents.chapter_writer import ChapterWriterAgent
from app.agents.document_parser import DocumentParserAgent
from app.agents.literature_agent import LiteratureAgent
from app.agents.narrative_agent import NarrativeAgent
from app.agents.outline_agent import OutlineAgent
from app.constants.style_types import StyleType
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
from app.services.citation_grounding import build_citation_policy_block, merge_grounding_for_writer
from app.services.citation_service import create_citation_from_paper, sync_bibliography_chapter
from app.services.figure_service import extract_and_store_figures, sync_figures_to_tiptap
from app.services.literature_query_refiner import refine_literature_query
from app.services.memory_service import build_book_memory, extract_chapter_memory
from app.services.preface_service import get_preface, set_preface
from app.services.section_assembler import process_chapter_generation_result
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


def _update_job(db, job: BookJob, *, step: BookJobStep | None = None, pct: int | None = None, status: BookJobStatus | None = None, error: str | None = None) -> None:
    if step is not None:
        job.current_step = step
    if pct is not None:
        job.progress_pct = pct
    if status is not None:
        job.status = status
    if error is not None:
        job.error_message = error
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
    from datetime import datetime, timezone
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


async def _write_chapter_sync(book_id: UUID, chapter_index: int, chat_model: str) -> None:
    db = SessionLocal()
    try:
        book = db.get(Book, book_id)
        ch = db.query(Chapter).filter(Chapter.book_id == book_id, Chapter.index == chapter_index).first()
        if not book or not ch:
            return
        total = int(db.query(func.count(Chapter.id)).filter(Chapter.book_id == book_id).scalar() or 0)
        ch.status = ChapterStatus.generating
        db.commit()

        memory = build_book_memory(book_id, chapter_index, db)
        from app.services.material_context import MaterialContextBuilder

        ctx = MaterialContextBuilder(db, book_id)
        summary_q = (ch.summary or "") + " " + ch.title
        rag_snippets = ctx.retrieve_for_chapter(summary_q.strip() or book.title, top_k=4)
        cite_blocks, rag_trimmed = merge_grounding_for_writer(db, book, rag_snippets, chapter_context=summary_q)
        memory["citation_policy"] = build_citation_policy_block(bool(cite_blocks), bool(rag_trimmed))
        st = (book.style_type or "").strip()
        memory["writer_temperature"] = 0.55 if st in (StyleType.popular_science.value, StyleType.insight_opinion.value) else 0.75

        chapter_dict = {
            "title": ch.title,
            "summary": ch.summary or "",
            "key_points": list((ch.content or {}).get("key_points") or []) if isinstance(ch.content, dict) else [],
            "sections": list((ch.content or {}).get("sections") or []) if isinstance(ch.content, dict) else [],
            "estimated_words": int((ch.content or {}).get("estimated_words") or 3000) if isinstance(ch.content, dict) else 3000,
            "chapter_index": chapter_index,
            "total_chapters": max(total, 1),
        }

        writer = ChapterWriterAgent()
        full_text = ""
        async for token in writer.stream(
            chapter_dict, memory, rag_trimmed, citation_blocks=cite_blocks, model=chat_model,
            temperature=memory.get("writer_temperature"),
        ):
            full_text += token

        meta = dict(ch.content) if isinstance(ch.content, dict) else {}
        outline_sections = meta.get("sections") or []
        try:
            tiptap_doc, md_text, wc = process_chapter_generation_result(
                full_text, chapter_index=chapter_index, outline_sections=outline_sections if isinstance(outline_sections, list) else [],
            )
        except Exception:
            md_text, wc, tiptap_doc = full_text, len(full_text), None
        meta["text"] = md_text
        if tiptap_doc:
            meta["tiptap_json"] = tiptap_doc
        ch.content = meta
        ch.word_count = wc
        ch.status = ChapterStatus.done
        db.commit()
        try:
            extract_and_store_figures(book_id, chapter_index, md_text, db)
            if md_text.strip():
                tiptap_doc = sync_figures_to_tiptap(book_id, chapter_index, md_text, db)
                meta["tiptap_json"] = tiptap_doc
                ch.content = meta
                db.commit()
        except Exception:
            logger.exception("figures extract failed")
        extract_chapter_memory(book_id, chapter_index, md_text, db)
    finally:
        db.close()


def run_auto_book_job(job_id: UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(BookJob, job_id)
        if not job or job.status not in (BookJobStatus.pending, BookJobStatus.running):
            return
        job.status = BookJobStatus.running
        db.commit()

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
        _infer_book_settings(book, writing_model)
        db.commit()

        _update_job(db, job, step=BookJobStep.literature, pct=20)
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

        _update_job(db, job, step=BookJobStep.outline, pct=35)
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
        outline = OutlineAgent().generate(cfg, snippets, model=outline_model)
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
        book.status = BookStatus.outline_ready
        db.commit()

        _update_job(db, job, step=BookJobStep.narrative, pct=50)
        _ensure_narrative_constitution_thread(book.id, constitution_model)
        db.expire_all()
        book = db.get(Book, job.book_id)

        _update_job(db, job, step=BookJobStep.preface, pct=55)

        chapters = db.query(Chapter).filter(Chapter.book_id == book.id).order_by(Chapter.index.asc()).all()
        n = len(chapters)
        for i, ch in enumerate(chapters):
            pct = 40 + int(55 * (i + 1) / max(n, 1))
            _update_job(db, job, step=BookJobStep.writing, pct=min(pct, 95))
            asyncio.run(_write_chapter_sync(book.id, ch.index, writing_model))

        _update_job(db, job, step=BookJobStep.bibliography, pct=98)
        sync_bibliography_chapter(db, book)

        book.status = BookStatus.writing
        _update_job(db, job, step=BookJobStep.done, pct=100, status=BookJobStatus.completed)
        _notify(
            db,
            user.id,
            "一键生成完成",
            f"《{book.title}》全部章节正文已生成，可进入编辑器配图与审校。",
            {"book_id": str(book.id), "job_id": str(job.id)},
        )
    except Exception as e:
        logger.exception("auto book job failed job=%s", job_id)
        job = db.get(BookJob, job_id)
        book = db.get(Book, job.book_id) if job else None
        if job:
            _update_job(db, job, status=BookJobStatus.failed, error=str(e)[:2000])
        if book:
            book.status = BookStatus.setup
            db.commit()
    finally:
        db.close()
