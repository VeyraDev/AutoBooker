from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.book import BookStatus, BookType, BookWorkflowMode
from app.models.chapter import Chapter
from app.models.optimization import (
    ManuscriptBaselineChapter,
    ManuscriptChapterMapping,
    ManuscriptRevision,
    OptimizationJob,
    OptimizationProject,
    OptimizationStatus,
)
from app.models.reference import FileLifecycleStatus, FilePurpose, ParseStatus, ReferenceFile, ReferenceFilePurpose
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.optimization import MappingConfirmIn, OptimizeChapterIn, OptimizationProjectOut
from app.services import book_service
from app.services.optimization_service import (
    build_diagnosis,
    create_revision,
    parse_optimization_source,
    revision_diff,
    run_optimization_job,
)
from app.services.markdown_to_tiptap import markdown_body_to_tiptap_blocks

router = APIRouter(prefix="/books", tags=["optimization"])


def _out(db: Session, project: OptimizationProject) -> OptimizationProjectOut:
    baselines = db.query(ManuscriptBaselineChapter).filter(
        ManuscriptBaselineChapter.project_id == project.id
    ).order_by(ManuscriptBaselineChapter.original_index).all()
    mappings = db.query(ManuscriptChapterMapping).filter(
        ManuscriptChapterMapping.project_id == project.id
    ).all()
    revisions = db.query(ManuscriptRevision).filter(
        ManuscriptRevision.project_id == project.id
    ).order_by(ManuscriptRevision.created_at.desc()).all()
    return OptimizationProjectOut(
        id=project.id,
        book_id=project.book_id,
        source_file_id=project.source_file_id,
        status=project.status.value,
        allow_structure_changes=project.allow_structure_changes,
        optimization_goals=list(project.optimization_goals or []),
        diagnosis=project.diagnosis,
        optimization_plan=project.optimization_plan,
        baseline_chapters=[
            {
                "id": str(x.id), "index": x.original_index, "title": x.title,
                "body_text": x.body_text, "source_locator": x.source_locator,
            } for x in baselines
        ],
        mappings=[
            {
                "id": str(x.id), "baseline_chapter_id": str(x.baseline_chapter_id),
                "working_chapter_id": str(x.working_chapter_id) if x.working_chapter_id else None,
                "outline_chapter_index": x.outline_chapter_index, "outline_title": x.outline_title,
                "confidence": x.confidence, "status": x.status, "reason": x.reason,
            } for x in mappings
        ],
        revisions=[
            {
                "id": str(x.id), "baseline_chapter_id": str(x.baseline_chapter_id),
                "status": x.status, "source": x.source, "summary": x.summary,
                "created_at": x.created_at.isoformat() if x.created_at else None,
            } for x in revisions
        ],
        error_message="优化任务未能继续，请稍后重试" if project.status == OptimizationStatus.failed else None,
    )


@router.post("/optimization-projects", response_model=OptimizationProjectOut, status_code=status.HTTP_201_CREATED)
async def create_optimization_project(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    goals: str = Form(default="[]"),
    allow_structure_changes: bool = Form(default=False),
    book_type: str = Form(default="nonfiction"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择原始书稿")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 PDF、DOCX、TXT")
    try:
        parsed_book_type = BookType(book_type)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不支持的书稿类型") from exc
    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "原始书稿不能为空")
    title = f"待优化：{Path(file.filename).stem}"[:500]
    book = book_service.create_book(
        user,
        {
            "title": title,
            "book_type": parsed_book_type,
            "workflow_mode": BookWorkflowMode.optimize_existing,
        },
        db,
    )
    ref = ReferenceFile(
        book_id=book.id,
        filename=file.filename,
        storage_path=None,
        file_type=suffix[1:],
        ingest_kind="material",
        parse_status=ParseStatus.processing,
        lifecycle_status=FileLifecycleStatus.processing,
        file_purposes=["source_manuscript"],
    )
    db.add(ref)
    db.flush()
    from app.services.assets.reference_asset_service import ReferenceAssetService

    ReferenceAssetService(db).attach_upload(ref=ref, content=content, owner_user_id=user.id)
    db.add(ReferenceFilePurpose(file_id=ref.id, purpose=FilePurpose.source_manuscript))
    try:
        parsed_goals = [str(x)[:300] for x in json.loads(goals) if str(x).strip()]
    except Exception:
        parsed_goals = []
    project = OptimizationProject(
        book_id=book.id, source_file_id=ref.id,
        allow_structure_changes=allow_structure_changes, optimization_goals=parsed_goals,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    background_tasks.add_task(parse_optimization_source, project.id)
    return _out(db, project)


@router.get("/{book_id}/optimization", response_model=OptimizationProjectOut)
def get_optimization(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    project = db.query(OptimizationProject).filter(OptimizationProject.book_id == book_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "优化项目不存在")
    return _out(db, project)


@router.post("/{book_id}/optimization/mapping/confirm", response_model=OptimizationProjectOut)
def confirm_mapping(book_id: UUID, body: MappingConfirmIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book = book_service.get_book_or_404(book_id, user, db)
    project = db.query(OptimizationProject).filter(OptimizationProject.book_id == book_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "优化项目不存在")
    for patch in body.mappings:
        row = db.query(ManuscriptChapterMapping).filter(
            ManuscriptChapterMapping.project_id == project.id,
            ManuscriptChapterMapping.baseline_chapter_id == patch.baseline_chapter_id,
        ).first()
        if row:
            row.outline_chapter_index = patch.outline_chapter_index
            row.outline_title = patch.outline_title
            row.status = "confirmed" if patch.confirmed else "needs_confirmation"
    if db.query(ManuscriptChapterMapping).filter(
        ManuscriptChapterMapping.project_id == project.id,
        ManuscriptChapterMapping.status == "needs_confirmation",
    ).count():
        raise HTTPException(status.HTTP_409_CONFLICT, "仍有章节对应关系需要确认")
    project.status = OptimizationStatus.ready_for_analysis
    project.baseline_confirmed_at = datetime.now(timezone.utc)
    source_file = db.get(ReferenceFile, project.source_file_id)
    if source_file:
        source_file.lifecycle_status = FileLifecycleStatus.effective
    book.status = BookStatus.writing
    db.commit()
    return _out(db, project)


@router.post("/{book_id}/optimization/diagnose", response_model=OptimizationProjectOut)
def diagnose(book_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    project = db.query(OptimizationProject).filter(OptimizationProject.book_id == book_id).first()
    if not project or project.status not in {OptimizationStatus.ready_for_analysis, OptimizationStatus.plan_ready}:
        raise HTTPException(status.HTTP_409_CONFLICT, "请先确认章节对应关系")
    build_diagnosis(db, project)
    return _out(db, project)


@router.post("/{book_id}/optimization/chapters", response_model=dict)
def optimize_chapter(book_id: UUID, body: OptimizeChapterIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    project = db.query(OptimizationProject).filter(OptimizationProject.book_id == book_id).first()
    if not project or project.status not in {OptimizationStatus.plan_ready, OptimizationStatus.editing}:
        raise HTTPException(status.HTTP_409_CONFLICT, "请先生成优化方案")
    row = create_revision(db, project, body.baseline_chapter_id, body.instruction)
    return {"id": str(row.id), "status": row.status}


@router.post("/{book_id}/optimization/run", response_model=dict)
def optimize_all(book_id: UUID, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    project = (
        db.query(OptimizationProject)
        .filter(OptimizationProject.book_id == book_id)
        .with_for_update()
        .first()
    )
    if not project or project.status not in {OptimizationStatus.plan_ready, OptimizationStatus.editing}:
        raise HTTPException(status.HTTP_409_CONFLICT, "请先生成优化方案")
    active = db.query(OptimizationJob).filter(
        OptimizationJob.project_id == project.id, OptimizationJob.status.in_(("pending", "running"))
    ).first()
    if active:
        return {"id": str(active.id), "status": active.status}
    job = OptimizationJob(project_id=project.id, job_type="full_book")
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_optimization_job, job.id)
    return {"id": str(job.id), "status": job.status}


@router.get("/{book_id}/optimization/jobs/{job_id}", response_model=dict)
def optimization_job(book_id: UUID, job_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    project = db.query(OptimizationProject).filter(OptimizationProject.book_id == book_id).first()
    job = db.get(OptimizationJob, job_id)
    if not project or not job or job.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return {
        "id": str(job.id), "status": job.status, "progress_pct": job.progress_pct,
        "current_chapter_index": job.current_chapter_index,
        "error_message": "优化任务未能继续，请稍后重试" if job.status == "failed" else None,
    }


@router.get("/{book_id}/optimization/revisions/{revision_id}/compare", response_model=dict)
def compare_revision(book_id: UUID, revision_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    project = db.query(OptimizationProject).filter(OptimizationProject.book_id == book_id).first()
    revision = db.get(ManuscriptRevision, revision_id)
    if not project or not revision or revision.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "修订版本不存在")
    baseline = db.get(ManuscriptBaselineChapter, revision.baseline_chapter_id)
    return {"original": baseline.body_text, "revised": revision.body_text, "diff": revision_diff(baseline.body_text, revision.body_text)}


@router.post("/{book_id}/optimization/revisions/{revision_id}/{action}", response_model=dict)
def decide_revision(book_id: UUID, revision_id: UUID, action: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    project = db.query(OptimizationProject).filter(OptimizationProject.book_id == book_id).first()
    revision = db.get(ManuscriptRevision, revision_id)
    if action not in {"accept", "reject"} or not project or not revision or revision.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "修订版本不存在")
    mapping = db.query(ManuscriptChapterMapping).filter(
        ManuscriptChapterMapping.baseline_chapter_id == revision.baseline_chapter_id
    ).first()
    if action == "accept":
        chapter = db.get(Chapter, mapping.working_chapter_id) if mapping else None
        if chapter:
            chapter.content = {"text": revision.body_text, "tiptap_json": revision.tiptap_json}
            chapter.word_count = len(revision.body_text)
        revision.status = "accepted"
    else:
        revision.status = "rejected"
    revision.decided_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": str(revision.id), "status": revision.status}


@router.post("/{book_id}/optimization/chapters/{baseline_id}/restore", response_model=dict)
def restore_baseline(book_id: UUID, baseline_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    book_service.get_book_or_404(book_id, user, db)
    project = db.query(OptimizationProject).filter(OptimizationProject.book_id == book_id).first()
    baseline = db.get(ManuscriptBaselineChapter, baseline_id)
    if not project or not baseline or baseline.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "原稿章节不存在")
    mapping = db.query(ManuscriptChapterMapping).filter(
        ManuscriptChapterMapping.baseline_chapter_id == baseline.id
    ).first()
    chapter = db.get(Chapter, mapping.working_chapter_id) if mapping else None
    if chapter:
        chapter.content = {
            "text": baseline.body_text,
            "tiptap_json": {
                "type": "doc",
                "content": markdown_body_to_tiptap_blocks(baseline.body_text),
            },
        }
        chapter.word_count = len(baseline.body_text)
    db.commit()
    return {"restored": True}
