from __future__ import annotations

import difflib
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import fitz
from docx import Document
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.llm.client import LLMClient
from app.models.book import Book, BookStatus
from app.models.chapter import Chapter, ChapterStatus
from app.models.optimization import (
    ManuscriptBaselineChapter,
    ManuscriptChapterMapping,
    ManuscriptRevision,
    OptimizationJob,
    OptimizationProject,
    OptimizationStatus,
)
from app.models.reference import FileLifecycleStatus, ParseStatus, ReferenceFile
from app.services.markdown_to_tiptap import markdown_body_to_tiptap_blocks

logger = logging.getLogger(__name__)

_HEADING = re.compile(
    r"^(?:#{1,6}\s+|第[一二三四五六七八九十百千\d]+章(?:\s+|[:：]\s*)|"
    r"Chapter\s+\d+(?:\s+|[:：]\s*))(.+)$",
    re.I,
)


def _sections_from_lines(lines: list[tuple[str, int, dict]]) -> list[dict]:
    sections: list[dict] = []
    current: dict | None = None
    for text, level, locator in lines:
        value = text.strip()
        if not value:
            continue
        match = _HEADING.match(value)
        is_heading = level > 0 or bool(match)
        if is_heading and len(value) <= 160:
            if current:
                current["body"] = "\n\n".join(current.pop("_body")).strip()
                sections.append(current)
            title = (match.group(1) if match else value).strip()
            current = {
                "title": title,
                "level": max(1, level),
                "locator": locator,
                "confidence": 100 if level > 0 else 85,
                "_body": [],
            }
        elif current:
            current["_body"].append(value)
        else:
            current = {
                "title": "正文",
                "level": 1,
                "locator": locator,
                "confidence": 45,
                "_body": [value],
            }
    if current:
        current["body"] = "\n\n".join(current.pop("_body")).strip()
        sections.append(current)
    return sections or [{"title": "正文", "level": 1, "locator": {}, "body": "", "confidence": 30}]


def extract_manuscript_sections(path: str, file_type: str) -> list[dict]:
    if file_type == "docx":
        doc = Document(path)
        lines: list[tuple[str, int, dict]] = []
        for i, p in enumerate(doc.paragraphs):
            style = (p.style.name if p.style else "").lower()
            match = re.search(r"(?:heading|标题)\s*(\d+)", style)
            lines.append((p.text, int(match.group(1)) if match else 0, {"paragraph": i + 1}))
        return _sections_from_lines(lines)
    if file_type == "pdf":
        doc = fitz.open(path)
        lines = []
        try:
            for page_no, page in enumerate(doc, start=1):
                data = page.get_text("dict")
                spans = [
                    span
                    for block in data.get("blocks", [])
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                    if str(span.get("text") or "").strip()
                ]
                normal = sorted([float(s.get("size") or 0) for s in spans])
                median = normal[len(normal) // 2] if normal else 11
                for span in spans:
                    size = float(span.get("size") or median)
                    level = 1 if size >= median * 1.35 else 0
                    lines.append((str(span.get("text") or ""), level, {"page": page_no}))
        finally:
            doc.close()
        return _sections_from_lines(lines)
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return _sections_from_lines([(line, 0, {"line": i + 1}) for i, line in enumerate(text.splitlines())])


def parse_optimization_source(project_id: UUID) -> None:
    db = SessionLocal()
    try:
        project = db.get(OptimizationProject, project_id)
        if not project:
            return
        ref = db.get(ReferenceFile, project.source_file_id)
        book = db.get(Book, project.book_id)
        if not ref or not book:
            raise RuntimeError("优化项目文件不存在")
        sections = extract_manuscript_sections(ref.storage_path, ref.file_type)
        db.query(ManuscriptChapterMapping).filter(ManuscriptChapterMapping.project_id == project.id).delete()
        db.query(ManuscriptBaselineChapter).filter(ManuscriptBaselineChapter.project_id == project.id).delete()
        db.query(Chapter).filter(Chapter.book_id == book.id).delete()
        db.flush()
        for i, item in enumerate(sections, start=1):
            body = str(item.get("body") or "")
            baseline = ManuscriptBaselineChapter(
                project_id=project.id,
                original_index=i,
                title=str(item.get("title") or f"第{i}章")[:500],
                heading_level=int(item.get("level") or 1),
                body_text=body,
                source_locator=item.get("locator") or {},
                content_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            )
            db.add(baseline)
            db.flush()
            tiptap = {"type": "doc", "content": markdown_body_to_tiptap_blocks(body)}
            unresolved = [
                match.group(0)
                for match in re.finditer(
                    r"\([^)]+,\s*(?:19|20)\d{2}\)|\[\d{1,3}\]",
                    body,
                )
            ]
            chapter = Chapter(
                book_id=book.id,
                index=i,
                title=baseline.title,
                summary=None,
                content={
                    "text": body,
                    "tiptap_json": tiptap,
                    "unresolved_citations": unresolved,
                },
                word_count=len(re.sub(r"\s+", "", body)),
                status=ChapterStatus.done,
            )
            db.add(chapter)
            db.flush()
            db.add(
                ManuscriptChapterMapping(
                    project_id=project.id,
                    baseline_chapter_id=baseline.id,
                    working_chapter_id=chapter.id,
                    outline_chapter_index=i,
                    outline_title=baseline.title,
                    confidence=int(item.get("confidence") or 0),
                    status=(
                        "auto_confirmed"
                        if int(item.get("confidence") or 0) >= 80
                        else "needs_confirmation"
                    ),
                )
            )
        if book.title.startswith("待优化：") and sections:
            book.title = sections[0]["title"][:500]
        project.status = OptimizationStatus.mapping_review
        ref.parse_status = ParseStatus.done
        ref.lifecycle_status = (
            FileLifecycleStatus.pending_confirmation
            if any(int(item.get("confidence") or 0) < 80 for item in sections)
            else FileLifecycleStatus.effective
        )
        db.commit()
    except Exception as exc:
        logger.exception("optimization source parse failed project=%s", project_id)
        project = db.get(OptimizationProject, project_id)
        if project:
            project.status = OptimizationStatus.failed
            project.error_message = str(exc)[:2000]
            db.commit()
    finally:
        db.close()


def build_diagnosis(db: Session, project: OptimizationProject) -> dict:
    chapters = db.query(ManuscriptBaselineChapter).filter(
        ManuscriptBaselineChapter.project_id == project.id
    ).order_by(ManuscriptBaselineChapter.original_index).all()
    seen: dict[str, int] = {}
    duplicates: list[dict] = []
    citation_gaps: list[int] = []
    for chapter in chapters:
        for para in re.split(r"\n\s*\n", chapter.body_text):
            key = re.sub(r"\W+", "", para)
            if len(key) < 40:
                continue
            if key in seen:
                duplicates.append({"chapters": [seen[key], chapter.original_index], "excerpt": para[:120]})
            else:
                seen[key] = chapter.original_index
        if re.search(r"(研究表明|数据显示|调查显示)", chapter.body_text) and not re.search(r"\([^)]+,\s*\d{4}\)|\[\d+\]", chapter.body_text):
            citation_gaps.append(chapter.original_index)
    diagnosis = {
        "structure": {"chapter_count": len(chapters), "order_consistent": True},
        "duplicate_content": duplicates[:30],
        "citation_gaps": citation_gaps,
        "terminology": {"status": "needs_review"},
        "language": {"status": "chapter_review_available"},
    }
    project.diagnosis = diagnosis
    project.optimization_plan = {
        "steps": ["修复章节逻辑", "优化语言表达", "减少重复内容", "统一专业术语", "提示缺失引用"],
        "preserve_structure": not project.allow_structure_changes,
    }
    project.status = OptimizationStatus.plan_ready
    db.commit()
    return diagnosis


def _optimize_text(book: Book, chapter: ManuscriptBaselineChapter, goals: list[str], instruction: str) -> tuple[str, str]:
    prompt = f"""优化以下书稿章节。保留原意与事实，不编造来源，不输出说明。
书名：{book.title}
章节：{chapter.title}
优化目标：{'；'.join(goals) or '逻辑、语言、重复、术语与引用完整性'}
附加要求：{instruction or '无'}

原文：
{chapter.body_text}"""
    result = LLMClient().chat_completion(
        [{"role": "system", "content": "仅输出优化后的章节正文。"}, {"role": "user", "content": prompt}],
        max_tokens=12000,
        temperature=0.45,
    ).strip()
    return (result or chapter.body_text), "已按优化目标生成候选版本"


def create_revision(db: Session, project: OptimizationProject, baseline_id: UUID, instruction: str = "") -> ManuscriptRevision:
    baseline = db.get(ManuscriptBaselineChapter, baseline_id)
    book = db.get(Book, project.book_id)
    if not baseline or baseline.project_id != project.id or not book:
        raise ValueError("章节不存在")
    body, summary = _optimize_text(book, baseline, list(project.optimization_goals or []), instruction)
    revision = ManuscriptRevision(
        project_id=project.id,
        baseline_chapter_id=baseline.id,
        body_text=body,
        tiptap_json={"type": "doc", "content": markdown_body_to_tiptap_blocks(body)},
        summary=summary,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


def run_optimization_job(job_id: UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(OptimizationJob, job_id)
        project = db.get(OptimizationProject, job.project_id) if job else None
        if not job or not project:
            return
        job.status = "running"
        project.status = OptimizationStatus.optimizing
        db.commit()
        chapters = db.query(ManuscriptBaselineChapter).filter(
            ManuscriptBaselineChapter.project_id == project.id
        ).order_by(ManuscriptBaselineChapter.original_index).all()
        for i, chapter in enumerate(chapters, start=1):
            job.current_chapter_index = chapter.original_index
            job.progress_pct = int((i - 1) * 100 / max(1, len(chapters)))
            db.commit()
            create_revision(db, project, chapter.id)
        job.status = "completed"
        job.progress_pct = 100
        job.finished_at = datetime.now(timezone.utc)
        project.status = OptimizationStatus.editing
        db.commit()
    except Exception as exc:
        logger.exception("optimization job failed=%s", job_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)[:2000]
            job.finished_at = datetime.now(timezone.utc)
        if project:
            project.status = OptimizationStatus.failed
            project.error_message = str(exc)[:2000]
        db.commit()
    finally:
        db.close()


def revision_diff(original: str, revised: str) -> list[dict]:
    matcher = difflib.SequenceMatcher(a=original, b=revised)
    return [
        {"type": tag, "original": original[a1:a2], "revised": revised[b1:b2]}
        for tag, a1, a2, b1, b2 in matcher.get_opcodes()
    ]
