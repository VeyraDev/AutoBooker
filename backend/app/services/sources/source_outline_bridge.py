"""Outline generation context from confirmed contracts — NOT full SourceSegment dumps.

识别 ≠ 可用。仅消费：
- ReferenceFile primary outline
- WritingRequirement / OutlineConstraint
- book.ai_inferred_settings["outline_generation_context"]（助手 prepare_outline_context）
- 契约中点名的已确认 SourceSegment
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.material import ConfirmationStatus, OutlineConstraint, WritingRequirement
from app.models.source_segment import SourceSegment
from app.models.writing_basis import WritingBasis

_CHAPTER_LINE_RE = re.compile(
    r"^(?:第\s*[一二三四五六七八九十百千零〇两\d]+\s*章|[Cc]hapter\s+\d+|\d+[\.、．]\s*)\s*(.+)$"
)

USAGE_PRIMARY_OUTLINE = "primary_outline"
USAGE_REFERENCE_OUTLINE = "reference_outline"
USAGE_WRITING_REQUIREMENT = "writing_requirement"
USAGE_MANUSCRIPT_HINT = "manuscript_structure_hint"
USAGE_EXCLUDE = "exclude"

VALID_USAGES = frozenset(
    {
        USAGE_PRIMARY_OUTLINE,
        USAGE_REFERENCE_OUTLINE,
        USAGE_WRITING_REQUIREMENT,
        USAGE_MANUSCRIPT_HINT,
        USAGE_EXCLUDE,
    }
)


def _block(seg: SourceSegment) -> str:
    parts: list[str] = []
    if seg.summary:
        parts.append(str(seg.summary).strip())
    if seg.excerpt:
        parts.append(str(seg.excerpt).strip())
    text = "\n".join(p for p in parts if p)
    return text[:6000]


def parse_chapters_from_text(text: str) -> list[dict[str, Any]]:
    """Hint-only chapter parse — never treat as final primary without contract."""
    chapters: list[dict[str, Any]] = []
    for line in (text or "").splitlines():
        line = line.strip().lstrip("·•-—").strip()
        if not line:
            continue
        m = _CHAPTER_LINE_RE.match(line)
        if not m:
            continue
        title = m.group(1).strip() or line
        title = re.sub(r"^[\d一二三四五六七八九十]+[\.、．\s]+", "", title).strip() or title
        chapters.append(
            {
                "index": len(chapters) + 1,
                "title": title[:200],
                "summary": "",
                "key_points": [],
                "sections": [],
                "estimated_words": 3000,
            }
        )
        if len(chapters) >= 40:
            break
    return chapters


def _settings(book: Book) -> dict[str, Any]:
    raw = book.ai_inferred_settings if isinstance(book.ai_inferred_settings, dict) else {}
    return dict(raw)


def _save_settings(book: Book, settings: dict[str, Any]) -> None:
    book.ai_inferred_settings = settings


def confirm_source_usage(
    db: Session,
    book: Book,
    *,
    segment_id: UUID,
    usage: str,
) -> dict[str, Any]:
    usage = (usage or "").strip()
    if usage not in VALID_USAGES:
        raise ValueError(f"usage must be one of {sorted(VALID_USAGES)}")

    seg = (
        db.query(SourceSegment)
        .filter(SourceSegment.id == segment_id, SourceSegment.book_id == book.id)
        .first()
    )
    if not seg:
        raise ValueError("Segment not found")

    if usage == USAGE_EXCLUDE:
        seg.user_confirmed = False
        db.flush()
        return {"segment_id": str(segment_id), "usage": usage, "confirmed": False}

    seg.user_confirmed = True
    block = _block(seg)
    settings = _settings(book)
    confirmed = dict(settings.get("confirmed_source_usages") or {})
    confirmed[str(segment_id)] = {
        "usage": usage,
        "segment_type": seg.segment_type.value if seg.segment_type else None,
    }
    settings["confirmed_source_usages"] = confirmed
    _save_settings(book, settings)

    if usage == USAGE_WRITING_REQUIREMENT and block:
        for line in block.splitlines():
            line = line.strip().lstrip("·•-—*\t ").strip()
            if len(line) < 4:
                continue
            exists = (
                db.query(WritingRequirement.id)
                .filter(
                    WritingRequirement.book_id == book.id,
                    WritingRequirement.content == line[:2000],
                    WritingRequirement.active.is_(True),
                )
                .first()
            )
            if exists:
                continue
            db.add(
                WritingRequirement(
                    book_id=book.id,
                    source_file_id=None,
                    content=line[:2000],
                    category="source_segment",
                    strength="must",
                    scope="book",
                    active=True,
                    confirmation_status=ConfirmationStatus.effective,
                )
            )

    if usage == USAGE_PRIMARY_OUTLINE and block:
        chapters = parse_chapters_from_text(block)
        if chapters:
            # Soft lock titles via outline_constraints when chapter titles are parseable
            for ch in chapters:
                title = str(ch.get("title") or "").strip()
                if not title:
                    continue
                exists = (
                    db.query(OutlineConstraint.id)
                    .filter(
                        OutlineConstraint.book_id == book.id,
                        OutlineConstraint.chapter_title == title,
                        OutlineConstraint.active.is_(True),
                    )
                    .first()
                )
                if exists:
                    continue
                db.add(
                    OutlineConstraint(
                        book_id=book.id,
                        chapter_index=int(ch.get("index") or len(chapters)),
                        chapter_title=title[:500],
                        locked_sections=[],
                        active=True,
                    )
                )

    if usage in {USAGE_PRIMARY_OUTLINE, USAGE_MANUSCRIPT_HINT}:
        basis = (
            db.query(WritingBasis)
            .filter(WritingBasis.book_id == book.id)
            .order_by(WritingBasis.version.desc())
            .first()
        )
        if basis:
            policy = list(basis.outline_policy or [])
            if usage == USAGE_PRIMARY_OUTLINE:
                rule = "严格保留用户确认的主大纲章序与章标题，仅可补充摘要、要点与下级节"
            else:
                rule = "初稿仅作结构线索，不得整段扩写进大纲生成"
            if rule not in policy:
                policy.append(rule)
                basis.outline_policy = policy[:20]

    db.flush()
    return {"segment_id": str(segment_id), "usage": usage, "confirmed": True}


def prepare_outline_context(
    db: Session,
    book: Book,
    *,
    mode: str = "generate",
    primary_segment_ids: list[str] | None = None,
    requirement_segment_ids: list[str] | None = None,
    reference_outline_ids: list[str] | None = None,
    manuscript_policy: str = "omit",
    must_keep_chapter_titles: bool = True,
) -> dict[str, Any]:
    """Persist outline_generation_context for outline API to consume."""
    settings = _settings(book)
    confirmed = settings.get("confirmed_source_usages") or {}

    def _filter_ids(ids: list[str] | None, allowed_usages: set[str]) -> list[str]:
        out: list[str] = []
        for sid in ids or []:
            meta = confirmed.get(str(sid)) if isinstance(confirmed, dict) else None
            if isinstance(meta, dict) and meta.get("usage") in allowed_usages:
                out.append(str(sid))
            elif not meta and sid:
                # allow explicit prepare ids only if segment is user_confirmed True
                try:
                    uid = UUID(str(sid))
                except ValueError:
                    continue
                seg = (
                    db.query(SourceSegment)
                    .filter(SourceSegment.id == uid, SourceSegment.book_id == book.id)
                    .first()
                )
                if seg and seg.user_confirmed is True:
                    out.append(str(sid))
        return out

    # Auto-fill from confirmed map when ids omitted
    if primary_segment_ids is None:
        primary_segment_ids = [
            sid
            for sid, meta in (confirmed.items() if isinstance(confirmed, dict) else [])
            if isinstance(meta, dict) and meta.get("usage") == USAGE_PRIMARY_OUTLINE
        ]
    if requirement_segment_ids is None:
        requirement_segment_ids = [
            sid
            for sid, meta in (confirmed.items() if isinstance(confirmed, dict) else [])
            if isinstance(meta, dict) and meta.get("usage") == USAGE_WRITING_REQUIREMENT
        ]
    if reference_outline_ids is None:
        reference_outline_ids = [
            sid
            for sid, meta in (confirmed.items() if isinstance(confirmed, dict) else [])
            if isinstance(meta, dict) and meta.get("usage") == USAGE_REFERENCE_OUTLINE
        ]

    mp = (manuscript_policy or "omit").strip()
    if mp not in {"omit", "structure_hint_only"}:
        mp = "omit"

    contract = {
        "mode": (mode or "generate").strip() or "generate",
        "primary_ids": _filter_ids(primary_segment_ids, {USAGE_PRIMARY_OUTLINE}),
        "requirement_ids": _filter_ids(requirement_segment_ids, {USAGE_WRITING_REQUIREMENT}),
        "reference_outline_ids": _filter_ids(reference_outline_ids, {USAGE_REFERENCE_OUTLINE}),
        "manuscript_policy": mp,
        "must_keep_chapter_titles": bool(must_keep_chapter_titles),
    }
    if mp == "structure_hint_only":
        contract["manuscript_ids"] = [
            sid
            for sid, meta in (confirmed.items() if isinstance(confirmed, dict) else [])
            if isinstance(meta, dict) and meta.get("usage") == USAGE_MANUSCRIPT_HINT
        ]
    else:
        contract["manuscript_ids"] = []

    settings["outline_generation_context"] = contract
    _save_settings(book, settings)
    db.flush()
    return contract


def _load_segments(db: Session, book_id: UUID, ids: list[str]) -> list[SourceSegment]:
    out: list[SourceSegment] = []
    for sid in ids:
        try:
            uid = UUID(str(sid))
        except ValueError:
            continue
        seg = (
            db.query(SourceSegment)
            .filter(SourceSegment.id == uid, SourceSegment.book_id == book_id)
            .first()
        )
        if seg and seg.user_confirmed is not False:
            out.append(seg)
    return out


def materials_from_outline_contract(db: Session, book: Book) -> dict[str, Any]:
    """Build outline cfg material fields from contract only (no full library dump)."""
    settings = _settings(book)
    contract = settings.get("outline_generation_context")
    if not isinstance(contract, dict):
        return {
            "source_outline_blocks": [],
            "source_requirement_blocks": [],
            "source_manuscript_blocks": [],
            "source_writing_rules": [],
            "parsed_primary_outline": None,
            "contract": None,
        }

    primary_segs = _load_segments(db, book.id, list(contract.get("primary_ids") or []))
    req_segs = _load_segments(db, book.id, list(contract.get("requirement_ids") or []))
    ref_segs = _load_segments(db, book.id, list(contract.get("reference_outline_ids") or []))
    ms_segs: list[SourceSegment] = []
    if contract.get("manuscript_policy") == "structure_hint_only":
        ms_segs = _load_segments(db, book.id, list(contract.get("manuscript_ids") or []))

    outline_blocks = [_block(s) for s in primary_segs if _block(s)]
    # reference outline as soft blocks (not primary lock)
    ref_blocks = [_block(s) for s in ref_segs if _block(s)]
    requirement_blocks = [_block(s) for s in req_segs if _block(s)]
    manuscript_blocks = [_block(s)[:1500] for s in ms_segs if _block(s)]  # short hints only

    parsed: list[dict[str, Any]] | None = None
    for block in outline_blocks:
        parsed = parse_chapters_from_text(block) or None
        if parsed:
            break

    writing_rules: list[str] = []
    for block in requirement_blocks:
        for line in block.splitlines():
            line = line.strip().lstrip("·•-—*\t ").strip()
            if 4 <= len(line) <= 500 and line not in writing_rules:
                writing_rules.append(line)

    return {
        "source_outline_blocks": outline_blocks[:3],
        "source_reference_outline_blocks": ref_blocks[:2],
        "source_requirement_blocks": requirement_blocks[:5],
        "source_manuscript_blocks": manuscript_blocks[:2],
        "source_writing_rules": writing_rules[:30],
        "parsed_primary_outline": parsed,
        "contract": contract,
    }


# Backward-compatible name used by older tests — now contract-only / empty without contract
def collect_assistant_source_context(db: Session, book_id: UUID) -> dict[str, Any]:
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        return {
            "source_outline_blocks": [],
            "source_requirement_blocks": [],
            "source_manuscript_blocks": [],
            "source_writing_rules": [],
            "parsed_primary_outline": None,
            "segment_counts": {"total_usable": 0},
        }
    mats = materials_from_outline_contract(db, book)
    return {
        **mats,
        "segment_counts": {
            "outline": len(mats.get("source_outline_blocks") or []),
            "requirement": len(mats.get("source_requirement_blocks") or []),
            "manuscript": len(mats.get("source_manuscript_blocks") or []),
            "total_usable": 0,
        },
    }


def merge_primary_outline(
    reference_primary: list[dict[str, Any]] | None,
    source_primary: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if reference_primary:
        return reference_primary
    return source_primary


# Alias for older tests
_parse_chapters_from_text = parse_chapters_from_text
