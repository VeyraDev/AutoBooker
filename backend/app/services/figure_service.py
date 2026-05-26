"""Figure extraction, numbering, and TipTap sync."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.figure import Figure, FigureStatus, FigureType

ANNOTATION_PATTERNS: dict[FigureType, re.Pattern[str]] = {
    FigureType.flowchart: re.compile(r"\[FLOWCHART:\s*(.*?)\]", re.DOTALL),
    FigureType.chart: re.compile(r"\[CHART:\s*(.*?)\]", re.DOTALL),
    FigureType.figure: re.compile(r"\[FIGURE:\s*(.*?)\]", re.DOTALL),
    FigureType.screenshot: re.compile(r"\[SCREENSHOT:\s*(.*?)\]", re.DOTALL),
}

# Full annotation including brackets for replacement in text/tiptap
ANNOTATION_FULL_PATTERNS: dict[FigureType, re.Pattern[str]] = {
    FigureType.flowchart: re.compile(r"\[FLOWCHART:\s*.*?\]", re.DOTALL),
    FigureType.chart: re.compile(r"\[CHART:\s*.*?\]", re.DOTALL),
    FigureType.figure: re.compile(r"\[FIGURE:\s*.*?\]", re.DOTALL),
    FigureType.screenshot: re.compile(r"\[SCREENSHOT:\s*.*?\]", re.DOTALL),
}


def _extract_position_hint(content: str, match_start: int) -> str:
    preceding = content[:match_start]
    hint_match = re.search(r"[^。\n]{0,50}图[\d\-—]+[^。\n]{0,20}", preceding)
    return hint_match.group(0).strip() if hint_match else ""


def _collect_annotation_matches(content: str) -> list[tuple[int, FigureType, str]]:
    """Return (start_pos, type, raw_annotation) sorted by position in content."""
    hits: list[tuple[int, FigureType, str]] = []
    for fig_type, pattern in ANNOTATION_PATTERNS.items():
        for match in pattern.finditer(content):
            hits.append((match.start(), fig_type, match.group(1).strip()))
    hits.sort(key=lambda x: x[0])
    return hits


def _match_figure_for_annotation(
    fig_type: FigureType,
    raw: str,
    existing: list[Figure],
    used_ids: set[UUID],
) -> Figure | None:
    """按类型+描述匹配尚未占用的已有图记录（保留已生成/已上传的图）。"""
    raw_norm = raw.strip()
    for fig in existing:
        if fig.id in used_ids:
            continue
        if fig.figure_type != fig_type:
            continue
        if (fig.raw_annotation or "").strip() == raw_norm:
            return fig
    return None


def extract_and_store_figures(
    book_id: UUID,
    chapter_index: int,
    content: str,
    db: Session,
    *,
    preserve_approved: bool = False,
) -> int:
    """解析章节标注并增量写入 figures 表；不删除已生成/已上传/已批准的图。"""
    hits = _collect_annotation_matches(content)
    existing = get_chapter_figures(book_id, chapter_index, db)
    used_ids: set[UUID] = set()
    sort_base = 0
    matched = 0

    for start_pos, fig_type, raw in hits:
        sort_base += start_pos
        position_hint = _extract_position_hint(content, start_pos)
        fig = _match_figure_for_annotation(fig_type, raw, existing, used_ids)
        if fig:
            fig.figure_type = fig_type
            fig.raw_annotation = raw
            fig.position_hint = position_hint
            fig.sort_order = sort_base
            used_ids.add(fig.id)
            matched += 1
        else:
            row = Figure(
                book_id=book_id,
                chapter_index=chapter_index,
                figure_type=fig_type,
                status=FigureStatus.pending,
                raw_annotation=raw,
                position_hint=position_hint,
                sort_order=sort_base,
            )
            db.add(row)
            db.flush()
            used_ids.add(row.id)
            existing.append(row)
            matched += 1

    for fig in existing:
        if fig.id in used_ids:
            continue
        if preserve_approved and fig.status == FigureStatus.approved:
            continue
        if fig.status != FigureStatus.pending:
            continue
        db.delete(fig)

    db.commit()
    db.expire_all()
    _renumber_chapter_by_sort_order(book_id, chapter_index, db)
    return matched


def _walk_tiptap_figure_blocks(doc: dict[str, Any] | None, visit) -> None:
    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "figureBlock":
            fid = str((node.get("attrs") or {}).get("figureId") or "").strip()
            if fid:
                visit(fid)
        for child in node.get("content") or []:
            walk(child)

    if doc:
        walk(doc)


def _ordered_figure_ids_from_tiptap(doc: dict[str, Any] | None) -> list[str]:
    """TipTap 文档中 figureBlock 的出现顺序（用于图 1-1、1-2…）。"""
    ids: list[str] = []

    def visit(fid: str) -> None:
        ids.append(fid)

    _walk_tiptap_figure_blocks(doc, visit)
    return ids


def _figure_ids_in_tiptap(doc: dict[str, Any] | None) -> set[str]:
    return set(_ordered_figure_ids_from_tiptap(doc))


def _renumber_chapter_by_sort_order(
    book_id: UUID, chapter_index: int, db: Session
) -> None:
    """无 TipTap 时按 sort_order / created_at 编号。"""
    figures = get_chapter_figures(book_id, chapter_index, db)
    for idx, fig in enumerate(figures, start=1):
        fig.figure_number = f"{chapter_index}-{idx}"
        if fig.sort_order is None:
            fig.sort_order = idx * 1000
    db.commit()


def renumber_chapter_figures_from_tiptap(
    book_id: UUID,
    chapter_index: int,
    tiptap_json: dict[str, Any] | None,
    db: Session,
) -> None:
    """按本章 TipTap 中 figureBlock 顺序重编号。"""
    order = _ordered_figure_ids_from_tiptap(tiptap_json)
    if not order:
        _renumber_chapter_by_sort_order(book_id, chapter_index, db)
        return

    by_id = {
        str(f.id): f
        for f in db.query(Figure)
        .filter(Figure.book_id == book_id, Figure.chapter_index == chapter_index)
        .all()
    }
    linked: set[str] = set()
    for idx, raw_id in enumerate(order, start=1):
        fig = by_id.get(raw_id)
        if not fig:
            continue
        linked.add(raw_id)
        fig.figure_number = f"{chapter_index}-{idx}"
        fig.sort_order = idx * 1000

    tail = sorted(
        [f for fid, f in by_id.items() if fid not in linked],
        key=lambda f: (f.sort_order or 0, f.created_at),
    )
    base = len(linked)
    for offset, fig in enumerate(tail, start=1):
        n = base + offset
        fig.figure_number = f"{chapter_index}-{n}"
        fig.sort_order = n * 1000
    db.commit()


def renumber_figures(book_id: UUID, db: Session) -> None:
    """全书各章按 TipTap 文档顺序（若有）重算 figure_number。"""
    from app.models.chapter import Chapter

    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id)
        .order_by(Chapter.index)
        .all()
    )
    for ch in chapters:
        meta = ch.content if isinstance(ch.content, dict) else {}
        tiptap = meta.get("tiptap_json")
        if isinstance(tiptap, dict) and _ordered_figure_ids_from_tiptap(tiptap):
            renumber_chapter_figures_from_tiptap(book_id, ch.index, tiptap, db)
        else:
            _renumber_chapter_by_sort_order(book_id, ch.index, db)


def prune_orphan_chapter_figures(
    book_id: UUID,
    chapter_index: int,
    tiptap_json: dict[str, Any] | None,
    db: Session,
) -> int:
    """删除本章中未出现在 TipTap 文档里的 pending/generated 孤儿图（保留 approved）。"""
    linked = _figure_ids_in_tiptap(tiptap_json)
    if not linked:
        return 0
    linked_uuids: list[UUID] = []
    for raw in linked:
        try:
            linked_uuids.append(UUID(str(raw)))
        except ValueError:
            continue
    if not linked_uuids:
        return 0
    removed = (
        db.query(Figure)
        .filter(
            Figure.book_id == book_id,
            Figure.chapter_index == chapter_index,
            Figure.status != FigureStatus.approved,
            ~Figure.id.in_(linked_uuids),
        )
        .delete(synchronize_session=False)
    )
    if removed:
        db.commit()
        renumber_chapter_figures_from_tiptap(book_id, chapter_index, tiptap_json, db)
    return removed


def refresh_chapter_figures(
    book_id: UUID,
    chapter_index: int,
    tiptap_json: dict[str, Any] | None,
    db: Session,
) -> list[Figure]:
    """清理孤儿图、重编号，返回本章图表列表。"""
    prune_orphan_chapter_figures(book_id, chapter_index, tiptap_json, db)
    renumber_chapter_figures_from_tiptap(book_id, chapter_index, tiptap_json, db)
    figures = get_chapter_figures(book_id, chapter_index, db)
    for fig in figures:
        repair_figure_file(fig, db)
    return get_chapter_figures(book_id, chapter_index, db)


def get_figure_list(book_id: UUID, db: Session) -> list[dict[str, Any]]:
    figures = (
        db.query(Figure)
        .filter(Figure.book_id == book_id)
        .order_by(Figure.chapter_index, Figure.sort_order, Figure.created_at)
        .all()
    )
    return [
        {
            "id": str(f.id),
            "figure_number": f.figure_number,
            "type": f.figure_type.value,
            "status": f.status.value,
            "caption": f.caption,
            "chapter": f.chapter_index,
            "position_hint": f.position_hint,
            "file_url": f.file_url,
            "raw_annotation": f.raw_annotation,
        }
        for f in figures
    ]


def get_chapter_figures(book_id: UUID, chapter_index: int, db: Session) -> list[Figure]:
    return (
        db.query(Figure)
        .filter(Figure.book_id == book_id, Figure.chapter_index == chapter_index)
        .order_by(Figure.sort_order, Figure.created_at)
        .all()
    )


def _figure_file_version(fig: Figure) -> int:
    ts = fig.updated_at or fig.created_at
    if ts is not None:
        return int(ts.timestamp() * 1000)
    return 0


def figure_to_block_attrs(fig: Figure) -> dict[str, Any]:
    return {
        "figureId": str(fig.id),
        "figureType": fig.figure_type.value,
        "figureNumber": fig.figure_number or "",
        "caption": fig.caption or fig.raw_annotation or "",
        "status": fig.status.value,
        "fileUrl": fig.file_url or "",
        "rawAnnotation": fig.raw_annotation or "",
        "fileVersion": _figure_file_version(fig),
    }


def _figure_block_node(fig: Figure) -> dict[str, Any]:
    return {
        "type": "figureBlock",
        "attrs": figure_to_block_attrs(fig),
    }


def sync_figures_to_tiptap(
    book_id: UUID,
    chapter_index: int,
    content: str,
    db: Session,
) -> dict[str, Any]:
    """Build TipTap doc from markdown text, replacing annotations with figureBlock nodes."""
    from sqlalchemy import text

    lock_key = (book_id.int % (2**31 - 1), chapter_index)
    db.execute(text("SELECT pg_advisory_xact_lock(:k1, :k2)"), {"k1": lock_key[0], "k2": lock_key[1]})
    extract_and_store_figures(book_id, chapter_index, content, db)
    figures = get_chapter_figures(book_id, chapter_index, db)
    fig_by_pos: list[tuple[int, Figure]] = []
    for fig_type, pattern in ANNOTATION_PATTERNS.items():
        for match in pattern.finditer(content):
            # find matching figure by sort order among same-chapter figures
            pass

    # Build ordered figure queue from DB (same order as annotations in text)
    fig_queue = list(figures)
    fig_idx = 0

    # Collect all annotation spans in document order
    spans: list[tuple[int, int, FigureType]] = []
    for fig_type, pattern in ANNOTATION_FULL_PATTERNS.items():
        for match in pattern.finditer(content):
            spans.append((match.start(), match.end(), fig_type))
    spans.sort(key=lambda x: x[0])

    blocks: list[dict[str, Any]] = []
    cursor = 0
    for start, end, _ftype in spans:
        segment = content[cursor:start]
        if segment.strip():
            for para in segment.split("\n\n"):
                p = para.strip()
                if p:
                    blocks.append({"type": "paragraph", "content": [{"type": "text", "text": p}]})
        if fig_idx < len(fig_queue):
            blocks.append(_figure_block_node(fig_queue[fig_idx]))
            fig_idx += 1
        cursor = end

    tail = content[cursor:]
    if tail.strip():
        for para in tail.split("\n\n"):
            p = para.strip()
            if p:
                blocks.append({"type": "paragraph", "content": [{"type": "text", "text": p}]})

    if not blocks:
        blocks.append({"type": "paragraph", "content": []})

    return {"type": "doc", "content": blocks}


def repair_figure_file(fig: Figure, db: Session) -> Figure:
    """修复 Graphviz cairo 渲染遗留的 .cairo.png 与 DB 中 .png 路径不一致。"""
    if not fig.file_path:
        return fig
    path = Path(fig.file_path)
    if path.is_file():
        return fig
    alt = path.with_name(f"{path.stem}.cairo.png")
    if alt.is_file():
        alt.replace(path)
        fig.file_path = str(path.resolve())
        fig.file_url = f"/static/figures/{fig.book_id}/{path.name}"
        db.commit()
        db.refresh(fig)
    return fig


def get_figure_or_404(figure_id: UUID, book_id: UUID, db: Session) -> Figure:
    from fastapi import HTTPException, status

    fig = (
        db.query(Figure)
        .filter(Figure.id == figure_id, Figure.book_id == book_id)
        .first()
    )
    if not fig:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Figure not found")
    return fig
