"""Figure extraction, numbering, and TipTap sync."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.models.figure import Figure, FigureSource, FigureStatus, FigureType

ANNOTATION_PATTERNS: dict[FigureType, re.Pattern[str]] = {
    FigureType.flowchart: re.compile(r"\[FLOWCHART:\s*(.*?)\]", re.DOTALL),
    FigureType.chart: re.compile(r"\[CHART:\s*(.*?)\]", re.DOTALL),
    FigureType.figure: re.compile(
        r"\[(?:FIGURE|DIAGRAM):\s*(.*?)\]",
        re.DOTALL,
    ),
    FigureType.screenshot: re.compile(r"\[SCREENSHOT:\s*(.*?)\]", re.DOTALL),
}

# Full annotation including brackets for replacement in text/tiptap
ANNOTATION_FULL_PATTERNS: dict[FigureType, re.Pattern[str]] = {
    FigureType.flowchart: re.compile(r"\[FLOWCHART:\s*.*?\]", re.DOTALL),
    FigureType.chart: re.compile(r"\[CHART:\s*.*?\]", re.DOTALL),
    FigureType.figure: re.compile(r"\[(?:FIGURE|DIAGRAM):\s*.*?\]", re.DOTALL),
    FigureType.screenshot: re.compile(r"\[SCREENSHOT:\s*.*?\]", re.DOTALL),
}

_LEGACY_TAG_BY_TYPE: dict[FigureType, str | None] = {
    FigureType.flowchart: "FLOWCHART",
    FigureType.chart: "CHART",
    FigureType.figure: None,
    FigureType.screenshot: "SCREENSHOT",
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
    prune_unused: bool = True,
) -> int:
    """解析章节标注并增量写入 figures 表；默认删除正文中已不存在的图记录。"""
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
                figure_source=FigureSource.writing,
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
        if not prune_unused and fig.status != FigureStatus.pending:
            continue
        db.delete(fig)

    db.commit()
    db.expire_all()
    _renumber_chapter_by_sort_order(book_id, chapter_index, db)
    classify_chapter_figures(book_id, chapter_index, db)
    return matched


def classify_chapter_figures(book_id: UUID, chapter_index: int, db: Session) -> None:
    """提取占位符时不做分类；完整 Diagram Pipeline 延迟到 generate 时执行。"""
    return


def _figure_type_from_attrs(attrs: dict[str, Any]) -> FigureType:
    key = str(attrs.get("figureType") or "figure").lower()
    if key == "flowchart":
        return FigureType.flowchart
    if key == "chart":
        return FigureType.chart
    if key == "screenshot":
        return FigureType.screenshot
    return FigureType.figure


def _iter_tiptap_figure_block_nodes(doc: dict[str, Any] | None) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "figureBlock":
            nodes.append(node)
            return
        for child in node.get("content") or []:
            walk(child)

    if doc:
        walk(doc)
    return nodes


def resolve_figure_for_block(
    book_id: UUID,
    chapter_index: int,
    attrs: dict[str, Any],
    *,
    db: Session,
    figures_by_id: dict[str, Figure],
    existing: list[Figure],
    used: set[UUID],
) -> tuple[Figure, dict[str, Any]]:
    """为 figureBlock attrs 解析或创建 figures 表记录，并回写 figureId。"""
    attrs = dict(attrs or {})
    fid = str(attrs.get("figureId") or "").strip()
    raw = str(attrs.get("rawAnnotation") or attrs.get("caption") or "").strip()
    ftype = _figure_type_from_attrs(attrs)

    fig: Figure | None = None
    if fid:
        fig = figures_by_id.get(fid)
        if fig is None:
            try:
                fig = (
                    db.query(Figure)
                    .filter(Figure.id == UUID(fid), Figure.book_id == book_id)
                    .first()
                )
            except ValueError:
                fig = None
            if fig is not None:
                figures_by_id[str(fig.id)] = fig

    if fig is None and raw:
        for candidate in existing:
            if candidate.id in used:
                continue
            if candidate.figure_type == ftype and (candidate.raw_annotation or "").strip() == raw:
                fig = candidate
                break

    if fig is None:
        fig = Figure(
            book_id=book_id,
            chapter_index=chapter_index,
            figure_type=ftype,
            status=FigureStatus.pending,
            raw_annotation=raw or None,
            figure_source=FigureSource.writing,
        )
        db.add(fig)
        db.flush()
        existing.append(fig)
        figures_by_id[str(fig.id)] = fig

    used.add(fig.id)
    if raw and not (fig.raw_annotation or "").strip():
        fig.raw_annotation = raw

    new_id = str(fig.id)
    if fid != new_id:
        attrs["figureId"] = new_id

    return fig, attrs


def ensure_figure_blocks_persisted(
    book_id: UUID,
    chapter_index: int,
    tiptap_json: dict[str, Any] | None,
    db: Session,
) -> dict[str, Any] | None:
    """确保 TipTap 中每个 figureBlock 在 figures 表中有对应记录，并回写 figureId。"""
    if not isinstance(tiptap_json, dict) or tiptap_json.get("type") != "doc":
        return tiptap_json

    existing = get_chapter_figures(book_id, chapter_index, db)
    figures_by_id = {str(f.id): f for f in existing}
    used: set[UUID] = set()
    changed = False

    for node in _iter_tiptap_figure_block_nodes(tiptap_json):
        before_id = str((node.get("attrs") or {}).get("figureId") or "")
        _fig, attrs = resolve_figure_for_block(
            book_id,
            chapter_index,
            node.get("attrs") or {},
            db=db,
            figures_by_id=figures_by_id,
            existing=existing,
            used=used,
        )
        if str(attrs.get("figureId") or "") != before_id:
            changed = True
        node["attrs"] = attrs

    if changed or used:
        db.commit()
        renumber_chapter_figures_from_tiptap(book_id, chapter_index, tiptap_json, db)
    return tiptap_json


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
    from app.services.tiptap_convert import tiptap_json_to_markdown

    extract_text = ""
    if isinstance(tiptap_json, dict) and tiptap_json.get("type") == "doc":
        extract_text = tiptap_json_to_markdown(tiptap_json).strip()
    if not extract_text:
        ch = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.index == chapter_index)
            .first()
        )
        if ch and isinstance(ch.content, dict):
            stored = ch.content.get("text")
            if isinstance(stored, str):
                extract_text = stored.strip()
    if extract_text:
        extract_and_store_figures(
            book_id,
            chapter_index,
            extract_text,
            db,
            prune_unused=False,
        )

    prune_orphan_chapter_figures(book_id, chapter_index, tiptap_json, db)
    if isinstance(tiptap_json, dict):
        ensure_figure_blocks_persisted(book_id, chapter_index, tiptap_json, db)
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
    for fig in figures:
        repair_figure_file(fig, db)
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
            "svg_url": f.svg_url,
            "quality_report": (f.classification_json or {}).get("quality_report") if isinstance(f.classification_json, dict) else None,
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
        "svgUrl": fig.svg_url or "",
        "rawAnnotation": fig.raw_annotation or "",
        "fileVersion": _figure_file_version(fig),
    }


def _figure_block_node(fig: Figure) -> dict[str, Any]:
    return {
        "type": "figureBlock",
        "attrs": figure_to_block_attrs(fig),
    }


_PID_COMMENT_RE = re.compile(r"<!--\s*pid:[^>]+-->\s*", re.I)


def _strip_pid_comments(text: str) -> str:
    return _PID_COMMENT_RE.sub("", text or "").strip()


def is_chapter_body_empty(content: dict[str, Any] | None) -> bool:
    """正文是否实质为空（仅剩空白或段落 id 占位）。"""
    if not content or not isinstance(content, dict):
        return True
    text = _strip_pid_comments(str(content.get("text") or "")).strip()
    if len(text) > 40:
        return False
    tj = content.get("tiptap_json")
    if not isinstance(tj, dict) or tj.get("type") != "doc":
        return len(text) == 0
    if text and not (tj.get("content") or []):
        return False
    from app.services.tiptap_convert import tiptap_json_to_markdown

    md = _strip_pid_comments(tiptap_json_to_markdown(tj))
    if len(md) > 40:
        return False
    if _figure_ids_in_tiptap(tj):
        return False
    nodes = tj.get("content") or []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        ntype = node.get("type")
        if ntype in ("heading", "table", "bulletList", "orderedList", "codeBlock", "blockquote", "figureBlock"):
            return False
        if ntype == "paragraph":
            body = ""
            for child in node.get("content") or []:
                if isinstance(child, dict) and child.get("type") == "text":
                    body += str(child.get("text") or "")
            if body.strip():
                return False
    return True


def rebuild_chapter_body_from_figures(
    book_id: UUID,
    chapter_index: int,
    db: Session,
    *,
    book: Book | None = None,
) -> dict[str, Any]:
    """当章节正文丢失但图表库仍有记录时，从图表重建 TipTap 正文。"""
    from app.services.chapter_figure_table_normalize import (
        _make_para,
        _short_title,
        normalize_chapter_figures_tables,
    )

    figures = get_chapter_figures(book_id, chapter_index, db)
    if not figures:
        return {"tiptap_json": {"type": "doc", "content": [{"type": "paragraph"}]}, "text": "", "overview": []}

    blocks: list[dict[str, Any]] = []
    for fig in figures:
        repair_figure_file(fig, db)
        num = (fig.figure_number or f"{chapter_index}-0").strip()
        parts = num.split("-", 1)
        ch_n = parts[0] if parts else str(chapter_index)
        seq_n = parts[1] if len(parts) > 1 else "0"
        title = (fig.caption or fig.raw_annotation or "示意图").strip()
        short = _short_title(title, fallback="示意图")
        blocks.append(_make_para(f"如图{ch_n}-{seq_n}所示，{short}。"))
        blocks.append(_figure_block_node(fig))
        blocks.append(_make_para(f"图{ch_n}-{seq_n}：{short}", center=True))

    draft = {"type": "doc", "content": blocks}
    return normalize_chapter_figures_tables(book_id, chapter_index, draft, db, book=book)


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
    extract_and_store_figures(book_id, chapter_index, content, db, prune_unused=True)
    figures = get_chapter_figures(book_id, chapter_index, db)
    hits = _collect_annotation_matches(content)
    used_sync: set[UUID] = set()
    fig_queue: list[Figure] = []
    for _start, fig_type, raw in hits:
        fig = _match_figure_for_annotation(fig_type, raw, figures, used_sync)
        if fig:
            used_sync.add(fig.id)
            fig_queue.append(fig)
    fig_idx = 0

    # Collect all annotation spans in document order
    spans: list[tuple[int, int, FigureType]] = []
    for fig_type, pattern in ANNOTATION_FULL_PATTERNS.items():
        for match in pattern.finditer(content):
            spans.append((match.start(), match.end(), fig_type))
    spans.sort(key=lambda x: x[0])

    from app.services.markdown_to_tiptap import markdown_body_to_tiptap_blocks

    blocks: list[dict[str, Any]] = []
    cursor = 0
    for start, end, _ftype in spans:
        segment = content[cursor:start]
        if segment.strip():
            blocks.extend(markdown_body_to_tiptap_blocks(segment))
        if fig_idx < len(fig_queue):
            blocks.append(_figure_block_node(fig_queue[fig_idx]))
            fig_idx += 1
        cursor = end

    tail = content[cursor:]
    if tail.strip():
        blocks.extend(markdown_body_to_tiptap_blocks(tail))

    if not blocks:
        blocks.append({"type": "paragraph", "content": []})

    return {"type": "doc", "content": blocks}


def repair_figure_file(fig: Figure, db: Session) -> Figure:
    """修复遗留路径、同步规范目录下的 figure.svg / figure.png 与 DB URL。"""
    from app.services.figures.generation import sync_figure_urls_from_disk
    from app.services.figures.storage.manager import figure_storage

    changed = False

    def clear_missing_svg() -> bool:
        nonlocal changed
        if not getattr(fig, "svg_url", None):
            return False
        canonical_svg = figure_storage.svg_path(fig.book_id, fig.chapter_index, fig.id)
        if canonical_svg.is_file():
            return False
        legacy = figure_storage.legacy_dir(fig.book_id) / f"{fig.id.hex}.svg"
        if legacy.is_file():
            return False
        fig.svg_url = None
        changed = True
        return True

    canonical_png = figure_storage.png_path(fig.book_id, fig.chapter_index, fig.id)
    canonical_svg = figure_storage.svg_path(fig.book_id, fig.chapter_index, fig.id)
    if canonical_png.is_file() or canonical_svg.is_file():
        before_url = fig.file_url
        before_svg = fig.svg_url
        sync_figure_urls_from_disk(fig, chapter_index=fig.chapter_index)
        if fig.file_url != before_url or fig.svg_url != before_svg or not fig.file_path:
            changed = True
    elif fig.file_path:
        path = Path(fig.file_path)
        if path.is_file():
            clear_missing_svg()
            return fig if not changed else _commit_figure(fig, db)
        alt = path.with_name(f"{path.stem}.cairo.png")
        if alt.is_file():
            alt.replace(path)
            fig.file_path = str(path.resolve())
            fig.file_url = f"/static/figures/{fig.book_id}/{path.name}"
            changed = True
        elif fig.file_url:
            resolved = figure_storage.resolve_local_path(fig.file_url)
            if resolved and resolved.is_file():
                fig.file_path = str(resolved.resolve())
                changed = True
    clear_missing_svg()
    return _commit_figure(fig, db) if changed else fig


def _commit_figure(fig: Figure, db: Session) -> Figure:
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
