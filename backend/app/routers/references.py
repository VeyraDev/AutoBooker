"""Reference file upload, list, status, and RAG search (debug)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.material import MaterialConflict, MaterialTerm, OutlineConstraint, WritingRequirement
from app.models.citation import CitationEvidence
from app.models.reference import (
    FileLifecycleStatus,
    FilePurpose,
    OutlineUsage,
    ParseStatus,
    ReferenceChunk,
    ReferenceFile,
    ReferenceFilePurpose,
)
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.reference import (
    ParseStatusOut,
    ReferenceFileOut,
    ReferenceSearchHit,
    ReferenceSearchIn,
    ReferenceSearchOut,
    ReferenceConfirmIn,
    ReferenceUploadOut,
)
from app.services import book_service
from app.agents.document_parser import DocumentParserAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["references"])


def _run_parse_task(
    book_id: UUID,
    file_id: UUID,
    storage_path: str,
    file_type: str,
    ingest_hint: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        agent = DocumentParserAgent(db, book_id)
        forced = None
        if ingest_hint in ("material", "reference"):
            forced = ingest_hint
        agent.parse_and_store(file_id, storage_path, file_type, forced_class=forced)
    except Exception:
        logger.exception("background parse failed book=%s file=%s", book_id, file_id)
    finally:
        db.close()


ALLOWED = {".pdf", ".docx", ".txt"}


@router.post(
    "/{book_id}/references/upload",
    response_model=ReferenceUploadOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_reference(
    book_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ingest_hint: str | None = Form(default=None),
    file_purposes: str | None = Form(default=None),
    outline_usage: str | None = Form(default=None),
    user_note: str | None = Form(default=None),
    share_to_library: bool = Form(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Only {', '.join(sorted(ALLOWED))} are allowed",
        )
    hint = (ingest_hint or "auto").strip().lower()
    if hint not in ("auto", "material", "reference"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ingest_hint must be auto, material, or reference")

    parsed_purposes: list[str] | None = None
    if file_purposes:
        try:
            raw = json.loads(file_purposes)
            if isinstance(raw, list):
                aliases = {"reference": "reference_material"}
                valid = {p.value for p in FilePurpose}
                parsed_purposes = []
                for p in raw:
                    value = aliases.get(str(p), str(p))
                    if value in valid and value not in parsed_purposes:
                        parsed_purposes.append(value)
        except json.JSONDecodeError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "file_purposes must be JSON array")

    ou = None
    if outline_usage in ("primary", "reference"):
        ou = OutlineUsage(outline_usage)

    if suffix == ".pdf":
        file_type = "pdf"
    elif suffix == ".docx":
        file_type = "docx"
    else:
        file_type = "txt"

    from app.config import settings

    base = settings.upload_path / str(book.id)
    base.mkdir(parents=True, exist_ok=True)
    new_name = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    dest = base / new_name

    content = await file.read()

    parsed_purposes = parsed_purposes or ["reference_material"]
    if "source_manuscript" in parsed_purposes and len(parsed_purposes) > 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "原始书稿必须单独上传")
    if share_to_library and "bibliography" not in parsed_purposes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只有参考文献可授权用于公共书库")
    dest.write_bytes(content)

    ref = ReferenceFile(
        book_id=book.id,
        filename=file.filename,
        storage_path=str(dest),
        file_type=file_type,
        parse_status=ParseStatus.pending,
        share_to_library="pending" if share_to_library else "private",
        file_purposes=parsed_purposes,
        outline_usage=ou,
        user_note=(user_note or "").strip() or None,
        lifecycle_status=FileLifecycleStatus.processing,
    )
    db.add(ref)
    db.flush()
    for purpose in parsed_purposes:
        db.add(
            ReferenceFilePurpose(
                file_id=ref.id,
                purpose=FilePurpose(purpose),
                confidence=100,
                user_confirmed=True,
                is_primary=purpose == "outline" and ou == OutlineUsage.primary,
            )
        )
    db.commit()
    db.refresh(ref)

    background_tasks.add_task(
        _run_parse_task,
        book.id,
        ref.id,
        str(dest),
        file_type,
        hint if hint != "auto" else None,
    )

    return ReferenceUploadOut(
        id=ref.id,
        filename=ref.filename,
        file_type=ref.file_type,
        ingest_kind=ref.ingest_kind or "reference",
        parse_status=ParseStatusOut(ref.parse_status.value),
        message="uploaded, parsing in background",
        lifecycle_status=ref.lifecycle_status.value,
    )


@router.get("/{book_id}/references", response_model=list[ReferenceFileOut])
def list_references(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    rows = (
        db.query(ReferenceFile)
        .filter(ReferenceFile.book_id == book_id)
        .order_by(ReferenceFile.created_at.desc())
        .all()
    )
    pairs = (
        db.query(ReferenceChunk.file_id, func.count(ReferenceChunk.id))
        .filter(ReferenceChunk.book_id == book_id)
        .group_by(ReferenceChunk.file_id)
        .all()
    )
    cmap = {fid: int(n) for fid, n in pairs}
    conflicts = db.query(MaterialConflict).filter(
        MaterialConflict.book_id == book_id,
        MaterialConflict.status == "pending",
    ).all()
    by_file: dict[str, list[dict]] = {}
    for conflict in conflicts:
        payload = {
            "id": str(conflict.id),
            "type": conflict.conflict_type,
            "message": conflict.message,
            "details": conflict.details,
        }
        for fid in conflict.file_ids or []:
            by_file.setdefault(str(fid), []).append(payload)
    return [
        ReferenceFileOut.model_validate(r).model_copy(
            update={
                "chunk_count": cmap.get(r.id, 0),
                "lifecycle_status": r.lifecycle_status.value,
                "parse_artifacts": r.parse_artifacts if isinstance(r.parse_artifacts, dict) else None,
                "conflicts": by_file.get(str(r.id), []),
            }
        )
        for r in rows
        if r.lifecycle_status != FileLifecycleStatus.disabled
    ]


@router.delete("/{book_id}/references/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reference(
    book_id: UUID,
    file_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    ref = db.query(ReferenceFile).filter(ReferenceFile.id == file_id, ReferenceFile.book_id == book_id).first()
    if not ref:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reference not found")

    from app.models.optimization import OptimizationProject
    protected = db.query(OptimizationProject).filter(OptimizationProject.source_file_id == ref.id).first()
    if protected and protected.baseline_confirmed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "原稿基线已建立，不能删除原始书稿")

    if ref.parse_artifacts and isinstance(ref.parse_artifacts, dict):
        art = dict(ref.parse_artifacts)
        art["status"] = "disabled"
        ref.parse_artifacts = art

    now = datetime.now(timezone.utc)
    ref.lifecycle_status = FileLifecycleStatus.disabled
    ref.disabled_at = now
    db.query(ReferenceFilePurpose).filter(ReferenceFilePurpose.file_id == ref.id).update({"active": False})
    db.query(ReferenceChunk).filter(ReferenceChunk.file_id == ref.id).update({"active": False})
    db.query(CitationEvidence).filter(CitationEvidence.source_file_id == ref.id).update({"active": False})
    db.query(WritingRequirement).filter(WritingRequirement.source_file_id == ref.id).update({"active": False})
    db.query(MaterialTerm).filter(MaterialTerm.source_file_id == ref.id).update({"active": False})
    db.query(OutlineConstraint).filter(OutlineConstraint.source_file_id == ref.id).update({"active": False})
    db.query(MaterialConflict).filter(
        MaterialConflict.book_id == book_id,
        MaterialConflict.file_ids.contains([str(ref.id)]),
    ).update({"status": "disabled"}, synchronize_session=False)
    if ref.outline_usage == OutlineUsage.primary or (ref.file_purposes and "writing_requirements" in ref.file_purposes):
        book.constitution_stale = True

    storage = Path(ref.storage_path)
    if storage.is_file():
        try:
            storage.unlink()
        except OSError:
            logger.warning("failed to delete reference file on disk: %s", storage, exc_info=True)

    db.commit()


@router.get("/{book_id}/references/{file_id}/status", response_model=ReferenceFileOut)
def reference_status(
    book_id: UUID,
    file_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    ref = db.query(ReferenceFile).filter(ReferenceFile.id == file_id, ReferenceFile.book_id == book_id).first()
    if not ref:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reference not found")
    cnt = (
        db.query(func.count(ReferenceChunk.id))
        .filter(ReferenceChunk.file_id == file_id, ReferenceChunk.book_id == book_id)
        .scalar()
    )
    conflicts = db.query(MaterialConflict).filter(
        MaterialConflict.book_id == book_id,
        MaterialConflict.status == "pending",
        MaterialConflict.file_ids.contains([str(file_id)]),
    ).all()
    return ReferenceFileOut.model_validate(ref).model_copy(
        update={
            "chunk_count": int(cnt or 0),
            "lifecycle_status": ref.lifecycle_status.value,
            "parse_artifacts": ref.parse_artifacts if isinstance(ref.parse_artifacts, dict) else None,
            "conflicts": [
                {"id": str(c.id), "type": c.conflict_type, "message": c.message, "details": c.details}
                for c in conflicts
            ],
        }
    )


@router.patch("/{book_id}/references/{file_id}/confirm", response_model=ReferenceFileOut)
def confirm_reference(
    book_id: UUID,
    file_id: UUID,
    body: ReferenceConfirmIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    ref = db.query(ReferenceFile).filter(
        ReferenceFile.id == file_id,
        ReferenceFile.book_id == book_id,
        ReferenceFile.lifecycle_status != FileLifecycleStatus.disabled,
    ).first()
    if not ref:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    if body.purposes is not None:
        aliases = {"reference": "reference_material"}
        wanted = {aliases.get(p, p) for p in body.purposes}
        valid = {p.value for p in FilePurpose}
        if not wanted or not wanted <= valid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid purposes")
        db.query(ReferenceFilePurpose).filter(ReferenceFilePurpose.file_id == file_id).delete()
        for purpose in sorted(wanted):
            db.add(
                ReferenceFilePurpose(
                    file_id=file_id,
                    purpose=FilePurpose(purpose),
                    user_confirmed=True,
                    confidence=100,
                    is_primary=purpose == "outline" and bool(body.primary_outline),
                )
            )
        ref.file_purposes = sorted(wanted)
    if body.primary_outline is not None and "outline" in (ref.file_purposes or []):
        ref.outline_usage = OutlineUsage.primary if body.primary_outline else OutlineUsage.reference
        db.query(ReferenceFilePurpose).filter(
            ReferenceFilePurpose.file_id == file_id,
            ReferenceFilePurpose.purpose == FilePurpose.outline,
        ).update({"is_primary": bool(body.primary_outline)})
        db.query(OutlineConstraint).filter(
            OutlineConstraint.source_file_id == file_id,
        ).update({"active": bool(body.primary_outline)})
    affected_file_ids: set[UUID] = {file_id}
    for conflict_id, resolution in body.conflict_resolutions.items():
        try:
            cid = UUID(conflict_id)
        except ValueError:
            continue
        conflict = db.query(MaterialConflict).filter(
            MaterialConflict.id == cid,
            MaterialConflict.book_id == book_id,
        ).first()
        if conflict:
            affected_file_ids.update(
                UUID(value)
                for value in (conflict.file_ids or [])
                if value
            )
            conflict.status = "resolved"
            conflict.resolution = {"choice": resolution}
            conflict.resolved_at = datetime.now(timezone.utc)
            if conflict.conflict_type == "multiple_primary_outlines":
                try:
                    selected_id = UUID(resolution)
                except ValueError:
                    selected_id = None
                if selected_id and str(selected_id) in (conflict.file_ids or []):
                    affected = db.query(ReferenceFile).filter(
                        ReferenceFile.book_id == book_id,
                        ReferenceFile.id.in_([UUID(value) for value in conflict.file_ids]),
                    ).all()
                    for candidate in affected:
                        selected = candidate.id == selected_id
                        candidate.outline_usage = (
                            OutlineUsage.primary if selected else OutlineUsage.reference
                        )
                        db.query(ReferenceFilePurpose).filter(
                            ReferenceFilePurpose.file_id == candidate.id,
                            ReferenceFilePurpose.purpose == FilePurpose.outline,
                        ).update({"is_primary": selected})
                        db.query(OutlineConstraint).filter(
                            OutlineConstraint.source_file_id == candidate.id,
                        ).update({"active": selected})
    for affected_id in affected_file_ids:
        pending = db.query(MaterialConflict).filter(
            MaterialConflict.book_id == book_id,
            MaterialConflict.status == "pending",
            MaterialConflict.file_ids.contains([str(affected_id)]),
        ).count()
        affected_file = db.get(ReferenceFile, affected_id)
        if affected_file and affected_file.lifecycle_status != FileLifecycleStatus.disabled:
            affected_file.lifecycle_status = (
                FileLifecycleStatus.pending_confirmation
                if pending
                else FileLifecycleStatus.effective
            )
    db.commit()
    db.refresh(ref)
    cnt = db.query(func.count(ReferenceChunk.id)).filter(ReferenceChunk.file_id == file_id, ReferenceChunk.active.is_(True)).scalar()
    return ReferenceFileOut.model_validate(ref).model_copy(
        update={
            "chunk_count": int(cnt or 0),
            "lifecycle_status": ref.lifecycle_status.value,
            "parse_artifacts": ref.parse_artifacts if isinstance(ref.parse_artifacts, dict) else None,
            "conflicts": [],
        }
    )


@router.post("/{book_id}/references/search", response_model=ReferenceSearchOut)
def search_references(
    book_id: UUID,
    body: ReferenceSearchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    agent = DocumentParserAgent(db, book_id)
    snippets, pairs = agent.retrieve_with_meta(body.query, top_k=body.top_k)
    hits = [ReferenceSearchHit(content=c, filename=fn) for c, fn in pairs]
    return ReferenceSearchOut(snippets=snippets, hits=hits)
