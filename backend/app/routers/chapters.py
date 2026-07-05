"""Single chapter CRUD and SSE generation."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.chapter_writer import ChapterWriterAgent
from app.agents.document_parser import DocumentParserAgent
from app.constants.style_types import StyleType
from app.services.citation_grounding import (
    build_citation_policy_block,
    merge_grounding_for_writer,
)
from app.agents.narrative_agent import NarrativeAgent
from app.database import SessionLocal, get_db
from app.models.book import Book
from app.models.chapter import Chapter, ChapterStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.llm.client import LLMClient
from app.schemas.book import NarrativeEnsureOut
from app.schemas.chapter import (
    ChapterCreateIn,
    ChapterDedupeOut,
    ChapterOut,
    ChapterReorderIn,
    ChapterUpdate,
    SelectionEditIn,
    SelectionEditOut,
)
from app.services import book_service
from app.services.dedupe_service import DedupeService
from app.services.figure_service import (
    _collect_annotation_matches,
    extract_and_store_figures,
    renumber_figures,
    refresh_chapter_figures,
    sync_figures_to_tiptap,
)
from app.services.section_assembler import process_chapter_generation_result
from app.services.tiptap_convert import chapter_content_to_markdown
from app.services.memory_service import build_book_memory, extract_chapter_memory
from app.services.outline_text import serialize_book_outline_markdown

logger = logging.getLogger(__name__)
_SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")

router = APIRouter(prefix="/books", tags=["chapters"])


def _get_chapter(book_id: UUID, chapter_index: int, db: Session) -> Chapter:
    ch = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
        .first()
    )
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    return ch


def _chapter_payload(ch: Chapter, total_chapters: int) -> dict:
    from app.services.heading_formatter import normalize_outline_sections

    meta = ch.content if isinstance(ch.content, dict) else {}
    sections_raw = meta.get("sections") or []
    sections = (
        normalize_outline_sections([s for s in sections_raw if isinstance(s, dict)])
        if isinstance(sections_raw, list)
        else []
    )
    return {
        "title": ch.title,
        "summary": ch.summary or "",
        "key_points": list(meta.get("key_points") or []),
        "sections": sections,
        "estimated_words": int(meta.get("estimated_words") or 3000),
        "chapter_index": ch.index,
        "total_chapters": max(int(total_chapters), 1),
    }


def _safe_llm_error_message(exc: Exception, *, model: str) -> str:
    msg = str(exc).strip() or exc.__class__.__name__
    msg = _SECRET_RE.sub("sk-***", msg).replace("\r", " ").replace("\n", " ")
    if len(msg) > 500:
        msg = msg[:500].rstrip() + "..."
    logger.error("writing rules generation failed model=%s detail=%s", model, msg)
    return "未能准备写作规则，请稍后重试"


def _ensure_narrative_constitution_thread(book_id: UUID, chat_model: str) -> None:
    """独立 Session：可在 asyncio.to_thread 中调用，生成并写入 narrative_constitution。"""
    from app.services.outline_hash import compute_book_outline_hash

    db = SessionLocal()
    try:
        book = db.get(Book, book_id)
        if not book:
            return
        current_hash = compute_book_outline_hash(book_id, db)
        has_constitution = bool((book.narrative_constitution or "").strip())
        if (
            has_constitution
            and not book.constitution_stale
            and book.narrative_constitution_outline_hash == current_hash
        ):
            return
        n = db.query(func.count(Chapter.id)).filter(Chapter.book_id == book_id).scalar() or 0
        outline_md = serialize_book_outline_markdown(book_id, db)
        agent = NarrativeAgent()
        text = agent.generate_constitution(
            book,
            outline_md,
            chapter_count=max(int(n), 1),
            model=chat_model,
        )
        if not text.strip():
            raise RuntimeError(f"model {chat_model} returned empty narrative constitution")
        book.narrative_constitution = text
        book.narrative_constitution_outline_hash = current_hash
        book.constitution_stale = False
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("narrative constitution generation failed book=%s model=%s", book_id, chat_model)
        raise
    finally:
        db.close()


from app.llm.providers import resolve_book_constitution_model, resolve_book_writing_model


def _chat_model_for_book(book, user=None, db=None) -> str:
    """写作、审校等正文相关 LLM 场景。"""
    return resolve_book_writing_model(book, user=user, db=db)


def _constitution_model_for_book(book, user=None, db=None) -> str:
    return resolve_book_constitution_model(book, user=user, db=db)


def _writer_temperature_for_book(book: Book) -> float:
    st = (book.style_type or "").strip()
    if st in (StyleType.popular_science.value, StyleType.insight_opinion.value):
        return 0.55
    return 0.75


@router.post("/{book_id}/narrative/ensure", response_model=NarrativeEnsureOut)
def ensure_narrative_constitution(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """进入写作前同步生成叙事宪法（若尚未生成或大纲已变更）。"""
    from app.services.outline_hash import compute_book_outline_hash

    book = book_service.get_book_or_404(book_id, user, db)
    current_hash = compute_book_outline_hash(book_id, db)
    needs = (
        not (book.narrative_constitution or "").strip()
        or book.constitution_stale
        or book.narrative_constitution_outline_hash != current_hash
    )
    if not needs:
        return NarrativeEnsureOut(ok=True, generated=False)
    chat_model = _constitution_model_for_book(book, user, db)
    try:
        _ensure_narrative_constitution_thread(book_id, chat_model)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=_safe_llm_error_message(exc, model=chat_model),
        ) from exc
    db.expire_all()
    book_fresh = db.get(Book, book_id)
    if not book_fresh or not (book_fresh.narrative_constitution or "").strip():
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="未能准备写作规则，请稍后重试",
        )
    return NarrativeEnsureOut(ok=True, generated=True)


def _memory_background(book_id: UUID, chapter_index: int, text: str) -> None:
    db = SessionLocal()
    try:
        extract_chapter_memory(book_id, chapter_index, text, db)
    except Exception:
        logger.exception("memory extract failed book=%s ch=%s", book_id, chapter_index)
    finally:
        db.close()


def _reset_stuck_generating_chapter(book_id: UUID, chapter_index: int) -> None:
    """客户端断开或生成器异常退出时，避免章节永久卡在 generating。"""
    db = SessionLocal()
    try:
        row = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
            .first()
        )
        if row and row.status == ChapterStatus.generating:
            row.status = ChapterStatus.pending
            db.commit()
    except Exception:
        logger.exception("reset stuck generating failed book=%s ch=%s", book_id, chapter_index)
    finally:
        db.close()


@router.get("/{book_id}/chapters/{chapter_index}", response_model=ChapterOut)
def get_chapter(
    book_id: UUID,
    chapter_index: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    from app.services.citation_nodes import (
        has_internal_citation_markers,
        has_structured_citation_nodes,
        normalize_chapter_citations,
        refresh_book_citation_rendering,
    )
    from app.services.citation_service import sync_book_bibliography

    meta = ch.content if isinstance(ch.content, dict) else {}
    doc = meta.get("tiptap_json")
    if isinstance(doc, dict) and has_internal_citation_markers(doc):
        normalize_chapter_citations(db, book, ch)
        db.commit()
        db.refresh(ch)
    elif isinstance(doc, dict) and has_structured_citation_nodes(doc):
        refresh_book_citation_rendering(db, book)
        sync_book_bibliography(db, book, commit=False)
        db.commit()
        db.refresh(ch)
    return ch


@router.put("/{book_id}/chapters/{chapter_index}", response_model=ChapterOut)
def update_chapter(
    book_id: UUID,
    chapter_index: int,
    body: ChapterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    if body.title is not None:
        ch.title = body.title
    if body.summary is not None:
        ch.summary = body.summary
    if body.content is not None:
        if isinstance(body.content, dict):
            old = dict(ch.content) if isinstance(ch.content, dict) else {}
            incoming = dict(body.content)
            ch.content = {**old, **incoming}
        else:
            ch.content = body.content
    if body.content is not None:
        from app.services.citation_nodes import normalize_chapter_citations

        normalize_chapter_citations(db, book, ch)
    db.commit()
    db.refresh(ch)
    return ch


@router.post("/{book_id}/chapters", response_model=ChapterOut, status_code=status.HTTP_201_CREATED)
def create_chapter(
    book_id: UUID,
    body: ChapterCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    max_row = db.query(func.max(Chapter.index)).filter(Chapter.book_id == book_id).scalar()
    max_idx = int(max_row or 0)

    if body.insert_at is None:
        new_index = max_idx + 1
    else:
        new_index = body.insert_at
        if new_index > max_idx + 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "insert_at cannot exceed current chapter count + 1",
            )
        to_shift = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.index >= new_index)
            .order_by(Chapter.index.desc())
            .all()
        )
        for row in to_shift:
            row.index += 1

    meta = {"key_points": [], "sections": [], "estimated_words": 3000}
    ch = Chapter(
        book_id=book.id,
        index=new_index,
        title=body.title.strip(),
        summary=body.summary,
        content=meta,
        word_count=0,
        status=ChapterStatus.pending,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


@router.delete("/{book_id}/chapters/{chapter_index}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(
    book_id: UUID,
    chapter_index: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    db.delete(ch)
    rest = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.index > chapter_index)
        .order_by(Chapter.index.asc())
        .all()
    )
    for row in rest:
        row.index -= 1
    db.flush()
    from app.services.citation_nodes import refresh_book_citation_rendering
    from app.services.citation_service import sync_book_bibliography

    refresh_book_citation_rendering(db, book)
    sync_book_bibliography(db, book, commit=False)
    db.commit()
    return None


@router.patch("/{book_id}/chapters/reorder", response_model=list[ChapterOut])
def reorder_chapters(
    book_id: UUID,
    body: ChapterReorderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    all_ch = db.query(Chapter).filter(Chapter.book_id == book_id).all()
    if len(body.items) != len(all_ch):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "items must include every chapter exactly once",
        )
    id_set = {c.id for c in all_ch}
    for it in body.items:
        if it.chapter_id not in id_set:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown chapter_id")
    new_indices = sorted(it.new_index for it in body.items)
    n = len(all_ch)
    if new_indices != list(range(1, n + 1)):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "new_index values must be a permutation of 1..n",
        )
    offset = 100_000
    for ch in all_ch:
        ch.index = ch.index + offset
    db.flush()
    id_to_new = {it.chapter_id: it.new_index for it in body.items}
    for ch in all_ch:
        ch.index = id_to_new[ch.id]
    db.flush()
    from app.services.citation_nodes import refresh_book_citation_rendering
    from app.services.citation_service import sync_book_bibliography

    refresh_book_citation_rendering(db, book)
    sync_book_bibliography(db, book, commit=False)
    db.commit()
    renumber_figures(book_id, db)
    rows = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.index.asc()).all()
    return rows


@router.post("/{book_id}/chapters/{chapter_index}/cancel-generation", response_model=ChapterOut)
def cancel_generation(
    book_id: UUID,
    chapter_index: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """断流/刷新后目录卡在「生成中」时，将本章恢复为待生成（幂等）。"""
    book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    if ch.status == ChapterStatus.generating:
        ch.status = ChapterStatus.pending
        db.commit()
        db.refresh(ch)
    return ch


@router.post("/{book_id}/chapters/{chapter_index}/generate")
async def generate_chapter_stream(
    book_id: UUID,
    chapter_index: int,
    force_generate: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    book_id = book.id
    ch = _get_chapter(book_id, chapter_index, db)

    if not force_generate:
        from app.models.citation import Citation
        from app.constants.style_types import StyleType as ST

        cite_count = db.query(Citation).filter(Citation.book_id == book_id).count()
        st = (book.style_type or "").strip()
        min_cites = 1 if st in (ST.practical_guide.value, ST.reference_tool.value) else 0
        if st in (ST.popular_science.value, ST.insight_opinion.value):
            min_cites = 3
        if min_cites and cite_count < min_cites:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                    f"本书文献不足（当前 {cite_count} 条，建议至少 {min_cites} 条）。"
                "请先在文献搜索中勾选入库，或加 ?force_generate=true 继续生成。",
            )

    writer = ChapterWriterAgent()
    writing_model = _chat_model_for_book(book, user, db)
    constitution_model = _constitution_model_for_book(book, user, db)

    total_chapters = int(
        db.query(func.count(Chapter.id)).filter(Chapter.book_id == book_id).scalar() or 0
    )

    async def event_stream():
        row = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
            .first()
        )
        if not row:
            yield f"data: {json.dumps({'error': 'chapter_not_found'}, ensure_ascii=False)}\n\n"
            return
        try:
            row.status = ChapterStatus.generating
            db.commit()
            full_text = ""
            try:
                await asyncio.to_thread(_ensure_narrative_constitution_thread, book_id, constitution_model)
            except Exception as exc:
                detail = _safe_llm_error_message(exc, model=constitution_model)
                logger.exception(
                    "narrative constitution generation failed book=%s model=%s",
                    book_id,
                    constitution_model,
                )
                row = (
                    db.query(Chapter)
                    .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
                    .first()
                )
                if row:
                    row.status = ChapterStatus.pending
                    db.commit()
                yield f"data: {json.dumps({'error': 'narrative_failed', 'detail': detail}, ensure_ascii=False)}\n\n"
                return

            book_live = db.get(Book, book_id)
            if not book_live:
                logger.error("book %s not found in session after narrative ensure", book_id)
                row = (
                    db.query(Chapter)
                    .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
                    .first()
                )
                if row:
                    row.status = ChapterStatus.pending
                    db.commit()
                yield f"data: {json.dumps({'error': 'narrative_failed'}, ensure_ascii=False)}\n\n"
                return

            memory = build_book_memory(book_id, chapter_index, db)
            parser = DocumentParserAgent(db, book_id)
            summary_q = (ch.summary or "") + " " + ch.title
            rag_snippets = parser.retrieve(summary_q.strip() or (book_live.title or ""), top_k=4)
            cite_blocks, rag_trimmed = merge_grounding_for_writer(
                db,
                book_live,
                rag_snippets,
                chapter_context=summary_q,
            )
            memory["citation_policy"] = build_citation_policy_block(
                bool(cite_blocks), bool(rag_trimmed)
            )
            memory["writer_temperature"] = _writer_temperature_for_book(book_live)
            chapter_dict = _chapter_payload(ch, total_chapters)

            async for token in writer.stream(
                chapter_dict,
                memory,
                rag_trimmed,
                citation_blocks=cite_blocks,
                model=writing_model,
                temperature=memory.get("writer_temperature"),
            ):
                full_text += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            row = (
                db.query(Chapter)
                .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
                .first()
            )
            md_text = full_text
            if row:
                meta = dict(row.content) if isinstance(row.content, dict) else {}
                outline_sections = meta.get("sections") or []
                if not isinstance(outline_sections, list):
                    outline_sections = []
                tiptap_doc = None
                try:
                    tiptap_doc, md_text, wc = process_chapter_generation_result(
                        full_text,
                        chapter_index=chapter_index,
                        outline_sections=outline_sections,
                    )
                except Exception:
                    logger.exception("chapter assemble failed book=%s ch=%s", book_id, chapter_index)
                    md_text = full_text
                    wc = len(full_text)
                meta["text"] = md_text
                if tiptap_doc:
                    meta["tiptap_json"] = tiptap_doc
                row.content = meta
                row.word_count = wc
                row.status = ChapterStatus.done
                from app.services.citation_nodes import normalize_chapter_citations

                normalize_chapter_citations(db, book_live, row)
                db.commit()
                try:
                    extract_and_store_figures(book_id, chapter_index, md_text, db)
                    if md_text.strip() and _collect_annotation_matches(md_text):
                        tiptap_doc = sync_figures_to_tiptap(
                            book_id, chapter_index, md_text, db
                        )
                        meta["tiptap_json"] = tiptap_doc
                        row.content = meta
                        normalize_chapter_citations(db, book_live, row, doc=tiptap_doc)
                        db.commit()
                    elif tiptap_doc:
                        refresh_chapter_figures(book_id, chapter_index, tiptap_doc, db)
                except Exception:
                    logger.exception(
                        "extract figures failed book=%s ch=%s", book_id, chapter_index
                    )
                try:
                    import threading

                    from app.models.book_job import BookJob, BookJobStatus
                    from app.services.figure_batch_service import enqueue_auto_chapter_figures, run_figure_batch

                    auto_job = (
                        db.query(BookJob)
                        .filter(BookJob.book_id == book_id)
                        .order_by(BookJob.created_at.desc())
                        .first()
                    )
                    checkpoint = auto_job.checkpoint_json if auto_job and isinstance(auto_job.checkpoint_json, dict) else {}
                    auto_book = auto_job is not None and auto_job.status == BookJobStatus.completed
                    if checkpoint.get("ready_for_editor") or auto_book:
                        batch_id = enqueue_auto_chapter_figures(book_id, chapter_index)
                        if batch_id:
                            threading.Thread(
                                target=run_figure_batch,
                                args=(batch_id,),
                                daemon=True,
                                name=f"figure-batch-{batch_id}",
                            ).start()
                except Exception:
                    logger.exception("enqueue automatic chapter figures failed book=%s ch=%s", book_id, chapter_index)
            asyncio.create_task(
                asyncio.to_thread(_memory_background, book_id, chapter_index, md_text)
            )
            done_payload: dict = {"done": True, "markdown": md_text}
            if row:
                target = int(chapter_dict.get("estimated_words") or 0)
                if target and wc < int(target * 0.72):
                    done_payload["truncated"] = True
                    logger.warning(
                        "chapter output shorter than target book=%s ch=%s wc=%s target=%s",
                        book_id,
                        chapter_index,
                        wc,
                        target,
                    )
            yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
        except Exception:
            logger.exception("chapter generate failed")
            row = (
                db.query(Chapter)
                .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
                .first()
            )
            if row:
                row.status = ChapterStatus.pending
                db.commit()
            yield f"data: {json.dumps({'error': 'generation_failed'}, ensure_ascii=False)}\n\n"
        finally:
            try:
                await asyncio.to_thread(_reset_stuck_generating_chapter, book_id, chapter_index)
            except Exception:
                logger.warning(
                    "post-stream reset hook failed book=%s ch=%s",
                    book_id,
                    chapter_index,
                    exc_info=True,
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post(
    "/{book_id}/chapters/{chapter_index}/edit-selection",
    response_model=SelectionEditOut,
)
def edit_selection(
    book_id: UUID,
    chapter_index: int,
    body: SelectionEditIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """润色 / 扩写 / 缩写选中文本（非流式）。"""
    book = book_service.get_book_or_404(book_id, user, db)
    _get_chapter(book_id, chapter_index, db)
    client = LLMClient()
    chat_model = _chat_model_for_book(book, user, db)

    if body.mode == "dedupe":
        result = DedupeService().dedupe_text(
            body.text,
            client=client,
            chat_model=chat_model,
            context=body.context or "",
        )
        return SelectionEditOut(text=result.text, report=result.report)

    prompts = {
        "polish": "请润色以下文字，保持原意，使表达更流畅专业。只输出改写后的正文，不要解释。",
        "expand": "请扩写以下文字，增加必要细节与衔接，不要改变核心观点。只输出扩写结果。",
        "shrink": "请缩写以下文字，保留关键信息。只输出缩写结果。",
        "dedupe": (
            "请对以下文字做「降重」改写：在完整保留原意、事实与专业术语的前提下，"
            "调整句式与用词，降低与常见表述的雷同度，使表达更原创。"
            "不要添加新观点，不要删减关键信息。只输出改写后的正文。"
        ),
        "rewrite": "请按用户指令改写以下文字。只输出改写结果，不要解释。",
        "flowchart": (
            "根据用户选中的文字及章节上下文，生成一张 Graphviz 流程图（DOT 语法）。"
            "只输出 DOT 源码（可用 ```dot 或 ```graphviz 围栏包裹），不要解释。"
            "使用 digraph 语法；节点中文标签必须用双引号包裹，例如 \"大模型\"；"
            "逻辑清晰、层次分明。流程图与概念图均用 Graphviz。"
            "若需左右对比两列内容：图级 rankdir=LR，每个 subgraph cluster 内设 rankdir=TB，"
            "簇内节点用 -> 串联，对应行用 { rank=same; 左节点; 右节点; } 对齐，"
            "两簇首节点间加 style=invis,weight=100 的隐形边使左右并排。"
        ),
    }
    if body.mode not in prompts:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported mode: {body.mode}")

    ctx_block = ""
    if (body.context or "").strip():
        ctx_block = f"\n\n【章节上下文（供参考）】\n{body.context.strip()[:12000]}"

    if body.mode == "flowchart":
        system = (
            "你是技术写作助手，擅长用 Graphviz DOT 表达流程与概念结构。"
            "只输出 DOT 代码，不要 Markdown 标题或说明文字。"
        )
        instr = (body.instruction or "").strip() or "根据选中内容生成流程图。"
        user_msg = f"要求：{instr}{ctx_block}\n\n【选中正文】\n{body.text.strip()}"
    elif body.mode == "rewrite":
        system = "你是专业中文编辑，只输出改写结果，不要加引号、标题或前言。"
        instr = (body.instruction or "").strip() or "使表达更清晰、自然。"
        user_msg = f"改写要求：{instr}{ctx_block}\n\n---\n{body.text.strip()}"
    else:
        system = "你是专业中文编辑，只输出改写结果，不要加引号、标题或前言。"
        user_msg = f"{prompts[body.mode]}{ctx_block}\n\n---\n{body.text.strip()}"

    temp = 0.55 if body.mode == "dedupe" else 0.45
    out = client.chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        model=chat_model,
        max_tokens=4096,
        temperature=temp,
    )
    return SelectionEditOut(text=out.strip())


_DEDUPE_PROMPT = (
    "请对以下文字做「降重」改写：在完整保留原意、事实与专业术语的前提下，"
    "调整句式与用词，降低与常见表述的雷同度，使表达更原创。"
    "不要添加新观点，不要删减关键信息。保留原有 Markdown 结构（标题、列表、表格等）。"
    "只输出改写后的正文。"
)
_DEDUPE_CHUNK_CHARS = 8000


def _dedupe_markdown_chunks(md: str, client: LLMClient, chat_model: str) -> str:
    system = "你是专业中文编辑，只输出改写结果，不要加引号、标题或前言。"
    if len(md) <= _DEDUPE_CHUNK_CHARS:
        out = client.chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": f"{_DEDUPE_PROMPT}\n\n---\n{md.strip()}"}],
            model=chat_model,
            max_tokens=8192,
            temperature=0.55,
        )
        return out.strip()

    parts: list[str] = []
    buf: list[str] = []
    size = 0
    for para in md.split("\n\n"):
        chunk_len = len(para) + (2 if buf else 0)
        if buf and size + chunk_len > _DEDUPE_CHUNK_CHARS:
            parts.append("\n\n".join(buf))
            buf = [para]
            size = len(para)
        else:
            buf.append(para)
            size += chunk_len
    if buf:
        parts.append("\n\n".join(buf))

    rewritten: list[str] = []
    for part in parts:
        out = client.chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": f"{_DEDUPE_PROMPT}\n\n---\n{part.strip()}"}],
            model=chat_model,
            max_tokens=8192,
            temperature=0.55,
        )
        rewritten.append(out.strip())
    return "\n\n".join(rewritten)


@router.post(
    "/{book_id}/chapters/{chapter_index}/dedupe-chapter",
    response_model=ChapterDedupeOut,
)
def dedupe_chapter(
    book_id: UUID,
    chapter_index: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """对本章全文做降 AI 率改写（保留原意与 Markdown 结构）。"""
    book = book_service.get_book_or_404(book_id, user, db)
    ch = _get_chapter(book_id, chapter_index, db)
    content = ch.content if isinstance(ch.content, dict) else {}
    md = chapter_content_to_markdown(content)
    if not md.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "本章暂无正文")

    client = LLMClient()
    chat_model = _chat_model_for_book(book, user, db)
    result = DedupeService().dedupe_markdown(md, client=client, chat_model=chat_model)
    return ChapterDedupeOut(text=result.text, original_text=md, report=result.report)
