"""上传资料语义解析与冲突检测。"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.llm.client import LLMClient
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(
    r"^(第[一二三四五六七八九十百千\d]+[章节篇部]|Chapter\s+\d+|[\d]+[\.\)、]\s*|\#{1,3}\s+)(.+)$",
    re.IGNORECASE,
)


def _extract_outline_candidate(text: str) -> list[dict[str, Any]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    chapters: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for ln in lines[:400]:
        m = _HEADING_RE.match(ln)
        if m and len(m.group(2)) < 120:
            if current:
                chapters.append(current)
            current = {"title": m.group(2).strip(), "sections": [], "key_points": []}
        elif current and len(ln) < 200 and not m:
            if ln.startswith(("-", "•", "*", "·")) or re.match(r"^\d+[\.\)、]", ln):
                current.setdefault("key_points", []).append(ln.lstrip("-•*· ").strip())
    if current:
        chapters.append(current)
    for i, ch in enumerate(chapters, start=1):
        ch["index"] = i
    return chapters[:40]


def parse_file_artifacts(
    text: str,
    filename: str,
    file_purposes: list[str],
    user_note: str = "",
    *,
    model: str | None = None,
) -> dict[str, Any]:
    """返回 parse_artifacts JSON 结构。"""
    purposes = file_purposes or ["reference_material"]
    excerpt = text[:12000]
    outline_candidate = _extract_outline_candidate(text) if "outline" in purposes else []
    writing_rules: list[str] = []
    terminology: list[dict[str, str]] = []

    if "writing_requirements" in purposes:
        try:
            client = LLMClient()
            prompt = f"""从以下文档摘录全书级写作要求（文风、术语、禁止事项等），输出 JSON：
{{"writing_rules":[{{"content":"...","category":"style|terminology|length|prohibited|other","strength":"must|should|preference","scope":"book|chapter","chapter_index":null}}],
"terminology":[{{"term":"...","definition":"...","type":"domain_term|theory|proper_noun|person|organization|user_defined"}}]}}
文件名：{filename}
用户备注：{user_note or "无"}

文档摘录：
{excerpt[:6000]}"""
            out = client.chat_completion(
                [
                    {"role": "system", "content": "只输出 JSON"},
                    {"role": "user", "content": prompt},
                ],
                model=model,
                max_tokens=1500,
                temperature=0.2,
            )
            data = parse_llm_json(out)
            if isinstance(data.get("writing_rules"), list):
                writing_rules = data["writing_rules"][:30]
            if isinstance(data.get("terminology"), list):
                terminology = [
                    {
                        "term": str(t.get("term", ""))[:80],
                        "definition": str(t.get("definition", ""))[:300],
                        "type": str(t.get("type") or "domain_term")[:40],
                    }
                    for t in data["terminology"]
                    if isinstance(t, dict) and t.get("term")
                ][:40]
        except Exception as exc:
            logger.warning("writing rules extract failed: %s", exc)
            if user_note:
                writing_rules = [{"content": user_note[:2000], "category": "other", "strength": "must", "scope": "book"}]

    return {
        "status": "candidate",
        "filename": filename,
        "purposes": purposes,
        "user_note": user_note or None,
        "outline_candidate": outline_candidate,
        "writing_rules": writing_rules,
        "terminology": terminology,
        "paragraph_count": len([ln for ln in text.splitlines() if ln.strip()]),
        "reference_chunk_count": 0,
        "bibliography_count": 0,
        "pending_issues": [],
    }


def persist_file_artifacts(db, ref, artifacts: dict[str, Any]) -> None:
    """Persist source-aware products. Re-parsing replaces only this file's products."""
    from app.models.material import (
        ConfirmationStatus,
        MaterialTerm,
        OutlineConstraint,
        WritingRequirement,
    )

    db.query(WritingRequirement).filter(WritingRequirement.source_file_id == ref.id).delete()
    db.query(MaterialTerm).filter(MaterialTerm.source_file_id == ref.id).delete()
    db.query(OutlineConstraint).filter(OutlineConstraint.source_file_id == ref.id).delete()

    for raw in artifacts.get("writing_rules") or []:
        item = raw if isinstance(raw, dict) else {"content": str(raw)}
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        db.add(
            WritingRequirement(
                book_id=ref.book_id,
                source_file_id=ref.id,
                content=content[:4000],
                category=str(item.get("category") or "other")[:64],
                strength=str(item.get("strength") or "should")[:20],
                scope=str(item.get("scope") or "book")[:20],
                chapter_index=item.get("chapter_index") if isinstance(item.get("chapter_index"), int) else None,
                confirmation_status=ConfirmationStatus.effective,
            )
        )

    allowed_types = {"domain_term", "theory", "proper_noun", "person", "organization", "user_defined"}
    for item in artifacts.get("terminology") or []:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        term_type = str(item.get("type") or "domain_term")
        if not term or term_type not in allowed_types:
            continue
        db.add(
            MaterialTerm(
                book_id=ref.book_id,
                source_file_id=ref.id,
                term=term[:300],
                canonical_form=term[:300],
                definition=str(item.get("definition") or "")[:2000] or None,
                term_type=term_type,
                confirmation_status=ConfirmationStatus.effective,
            )
        )

    if getattr(ref, "outline_usage", None) and ref.outline_usage.value == "primary":
        for i, chapter in enumerate(artifacts.get("outline_candidate") or [], start=1):
            if not isinstance(chapter, dict) or not str(chapter.get("title") or "").strip():
                continue
            db.add(
                OutlineConstraint(
                    book_id=ref.book_id,
                    source_file_id=ref.id,
                    chapter_index=i,
                    chapter_title=str(chapter["title"])[:500],
                    locked_sections=chapter.get("sections") or [],
                )
            )
    db.flush()


def detect_primary_outline_conflicts(db, book_id) -> list[dict[str, Any]]:
    from app.models.reference import FileLifecycleStatus, OutlineUsage, ReferenceFile

    primaries = (
        db.query(ReferenceFile)
        .filter(
            ReferenceFile.book_id == book_id,
            ReferenceFile.outline_usage == OutlineUsage.primary,
            ReferenceFile.lifecycle_status != FileLifecycleStatus.disabled,
        )
        .all()
    )
    if len(primaries) <= 1:
        return []
    return [
        {
            "type": "multiple_primary_outlines",
            "status": "pending",
            "message": "存在多份「主大纲」文件，请选择采用哪一份。",
            "file_ids": [str(f.id) for f in primaries],
            "options": [{"id": str(f.id), "label": f.filename} for f in primaries],
        }
    ]


def sync_material_conflicts(db, book_id) -> list[dict[str, Any]]:
    from app.models.material import MaterialConflict, MaterialTerm, WritingRequirement
    from app.models.reference import FileLifecycleStatus, ReferenceFile

    conflicts = detect_primary_outline_conflicts(db, book_id)
    db.query(MaterialConflict).filter(
        MaterialConflict.book_id == book_id,
        MaterialConflict.conflict_type.in_(
            ("multiple_primary_outlines", "word_count_conflict", "terminology_conflict")
        ),
        MaterialConflict.status == "pending",
    ).delete()

    length_rows = db.query(WritingRequirement).filter(
        WritingRequirement.book_id == book_id,
        WritingRequirement.active.is_(True),
        WritingRequirement.category == "length",
    ).all()
    targets: dict[int, set[str]] = {}
    for row in length_rows:
        numbers = re.findall(r"\d[\d,，]{2,}", row.content or "")
        if numbers:
            value = int(numbers[0].replace(",", "").replace("，", ""))
            targets.setdefault(value, set()).add(str(row.source_file_id))
    if len(targets) > 1:
        file_ids = sorted({fid for values in targets.values() for fid in values})
        conflicts.append(
            {
                "type": "word_count_conflict",
                "status": "pending",
                "message": "不同文件中的字数要求不一致，请选择采用的要求。",
                "file_ids": file_ids,
                "options": [{"value": value, "file_ids": sorted(ids)} for value, ids in targets.items()],
            }
        )

    terms = db.query(MaterialTerm).filter(
        MaterialTerm.book_id == book_id,
        MaterialTerm.active.is_(True),
    ).all()
    by_term: dict[str, list] = {}
    for term in terms:
        by_term.setdefault((term.term or "").casefold(), []).append(term)
    for label, rows in by_term.items():
        definitions = {
            (row.canonical_form or row.term or "", row.definition or "")
            for row in rows
        }
        if label and len(definitions) > 1:
            conflicts.append(
                {
                    "type": "terminology_conflict",
                    "status": "pending",
                    "message": f"术语“{rows[0].term}”存在不同写法或定义，请确认。",
                    "file_ids": sorted({str(row.source_file_id) for row in rows}),
                    "options": [
                        {"canonical_form": canonical, "definition": definition}
                        for canonical, definition in definitions
                    ],
                }
            )

    for item in conflicts:
        db.add(
            MaterialConflict(
                book_id=book_id,
                conflict_type=item["type"],
                message=item["message"],
                file_ids=item["file_ids"],
                details={"options": item["options"]},
            )
        )
        for file_id in item.get("file_ids") or []:
            row = db.get(ReferenceFile, file_id)
            if row:
                row.lifecycle_status = FileLifecycleStatus.pending_confirmation
    db.flush()
    return conflicts


def sync_primary_outline_conflicts(db, book_id) -> list[dict[str, Any]]:
    """Backward-compatible alias for callers outside the 0.5 ingestion flow."""
    return sync_material_conflicts(db, book_id)


def get_primary_outline_for_book(db, book_id) -> list[dict[str, Any]] | None:
    from app.models.reference import FileLifecycleStatus, OutlineUsage, ReferenceFile

    ref = (
        db.query(ReferenceFile)
        .filter(
            ReferenceFile.book_id == book_id,
            ReferenceFile.outline_usage == OutlineUsage.primary,
            ReferenceFile.lifecycle_status == FileLifecycleStatus.effective,
        )
        .order_by(ReferenceFile.created_at.desc())
        .first()
    )
    if not ref or not isinstance(ref.parse_artifacts, dict):
        return None
    cand = ref.parse_artifacts.get("outline_candidate")
    return cand if isinstance(cand, list) and cand else None


def get_book_level_writing_rules(db, book_id) -> list[str]:
    from app.models.material import ConfirmationStatus, WritingRequirement

    rules: list[str] = []
    rows = db.query(WritingRequirement).filter(
        WritingRequirement.book_id == book_id,
        WritingRequirement.active.is_(True),
        WritingRequirement.confirmation_status == ConfirmationStatus.effective,
        WritingRequirement.scope == "book",
    ).all()
    for row in rows:
        s = (row.content or "").strip()
        if s and s not in rules:
            rules.append(s)
    return rules[:40]


def merge_outline_with_primary(generated: dict[str, Any], primary: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Program-level guard: primary chapter count/order/title cannot drift."""
    if not primary:
        return generated
    generated_chapters = generated.get("chapters") or []
    out: list[dict[str, Any]] = []
    for i, locked in enumerate(primary, start=1):
        proposed = generated_chapters[i - 1] if i - 1 < len(generated_chapters) else {}
        locked_sections = locked.get("sections") or []
        proposed_sections = proposed.get("sections") or []
        sections = locked_sections if locked_sections else proposed_sections
        out.append(
            {
                **proposed,
                "index": i,
                "title": str(locked.get("title") or f"第{i}章"),
                "sections": sections,
                "summary": proposed.get("summary") or locked.get("summary") or "",
                "key_points": proposed.get("key_points") or locked.get("key_points") or [],
                "estimated_words": proposed.get("estimated_words") or locked.get("estimated_words") or 3000,
            }
        )
    return {**generated, "chapters": out}
