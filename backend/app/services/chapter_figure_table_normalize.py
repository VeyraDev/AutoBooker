"""本章图表与表格一键排序：重编号、补引用与题注。"""

from __future__ import annotations

import copy
import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.figure import Figure
from app.services.figure_service import (
    ensure_figure_blocks_persisted,
    get_chapter_figures,
    renumber_chapter_figures_from_tiptap,
    resolve_figure_for_block,
)
from app.services.markdown_to_tiptap import _parse_inline_bold
from app.services.table_caption_ai import suggest_figure_caption, suggest_table_caption
from app.services.tiptap_convert import _inline_to_markdown, tiptap_json_to_markdown

TABLE_CAPTION_RE = re.compile(r"^表\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]\s*(.+)$")
FIGURE_CAPTION_RE = re.compile(r"^图\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]\s*(.+)$")
FIG_REF_IN_TEXT_RE = re.compile(r"图\s*\d+\s*[-–—]\s*\d+")
TABLE_REF_IN_TEXT_RE = re.compile(r"表\s*\d+\s*[-–—]\s*\d+")


def _para_text(node: dict[str, Any] | None) -> str:
    if not isinstance(node, dict) or node.get("type") != "paragraph":
        return ""
    return _inline_to_markdown(node.get("content")).strip()


def _short_title(text: str, *, max_len: int = 48, fallback: str = "示意图") -> str:
    t = (text or "").strip()
    if not t:
        return fallback
    first = re.split(r"[。！？\n]", t)[0].strip()
    base = first if len(first) >= 6 else t
    if len(base) > max_len:
        return base[:max_len].rstrip() + "…"
    return base


_PROMPT_LIKE_RE = re.compile(
    r"\[(?:DIAGRAM|FIGURE|FLOWCHART|CHART|SCREENSHOT)\s*:|请.{0,12}(生成|绘制|画)|布局脚本|可见文字白名单|图类确认|用户原始输入|不要输出",
    re.I,
)
_GENERIC_TITLE_RE = re.compile(
    r"^(?:本章|章节|内容|整体|综合|核心|总体)?(?:总结|概览|概述|示意|结构|流程|关系|信息|要点)?[图表]$"
)


def _usable_caption_title(title: str, *, kind: str) -> str:
    t = (title or "").strip()
    if not t or len(t) > 32 or "\n" in t or _PROMPT_LIKE_RE.search(t):
        return ""
    t = re.sub(r"^(?:图|表)\s*\d+\s*[-–—－]\s*\d+\s*[:：]\s*", "", t).strip()
    if _GENERIC_TITLE_RE.match(t):
        return ""
    suffix = "表" if kind == "table" else "图"
    if not t.endswith(suffix):
        t = t.rstrip("表图") + suffix
    if len(t) > 32:
        t = t[:31].rstrip("表图") + suffix
    return t


def _caption_from_source(text: str, *, kind: str) -> str:
    source = (text or "").strip()
    if not source or _PROMPT_LIKE_RE.search(source[:120]):
        source = re.sub(r"^\[(?:DIAGRAM|FIGURE|FLOWCHART|CHART|SCREENSHOT)\s*:\s*", "", source, flags=re.I)
        source = re.sub(r"\]\s*$", "", source).strip()
    if not source or _GENERIC_TITLE_RE.match(source):
        return ""
    first = re.split(r"[。！？\n]", source, maxsplit=1)[0].strip()
    first = re.split(r"[，,；;：:]", first, maxsplit=1)[0].strip() or first
    return _usable_caption_title(_short_title(first, max_len=24, fallback=""), kind=kind)


def _first_specific_text(*values: str | None) -> str:
    for value in values:
        text = (value or "").strip()
        if text and not _GENERIC_TITLE_RE.match(text):
            return text
    return ""


def _figure_caption_fallback(attrs: dict[str, Any]) -> str:
    ftype = str(attrs.get("figureType") or "").lower()
    if ftype == "flowchart":
        return "流程示意图"
    if ftype == "chart":
        return "数据图"
    if ftype == "screenshot":
        return "界面截图"
    return "本章示意图"


def _make_para(text: str, *, center: bool = False) -> dict[str, Any]:
    node: dict[str, Any] = {
        "type": "paragraph",
        "content": _parse_inline_bold(text),
    }
    if center:
        node["attrs"] = {"textAlign": "center"}
    return node


def _replace_figure_ref(text: str, chapter_index: int, seq: int) -> str:
    target = f"图{chapter_index}-{seq}"
    if FIG_REF_IN_TEXT_RE.search(text):
        return FIG_REF_IN_TEXT_RE.sub(target, text, count=1)
    stripped = text.rstrip()
    if stripped and stripped[-1] in "。！？；":
        return f"{stripped[:-1]}，如图{chapter_index}-{seq}所示{stripped[-1]}"
    return f"{stripped}，如图{chapter_index}-{seq}所示。"


def _replace_table_ref(text: str, chapter_index: int, seq: int) -> str:
    target = f"表{chapter_index}-{seq}"
    if TABLE_REF_IN_TEXT_RE.search(text):
        return TABLE_REF_IN_TEXT_RE.sub(target, text, count=1)
    stripped = text.rstrip()
    if stripped and stripped[-1] in "。！？；":
        return f"{stripped[:-1]}，见{target}{stripped[-1]}"
    return f"{stripped}，见{target}。"


def _patch_para_text(node: dict[str, Any], new_text: str, *, center: bool | None = None) -> dict[str, Any]:
    out = copy.deepcopy(node)
    out["content"] = _parse_inline_bold(new_text)
    attrs = dict(out.get("attrs") or {})
    if center is True:
        attrs["textAlign"] = "center"
    elif center is False and "textAlign" in attrs:
        attrs.pop("textAlign", None)
    if attrs:
        out["attrs"] = attrs
    elif "attrs" in out:
        out.pop("attrs", None)
    return out


def _is_figure_caption_para(node: dict[str, Any] | None) -> bool:
    return bool(FIGURE_CAPTION_RE.match(_para_text(node)))


def _is_table_caption_para(node: dict[str, Any] | None) -> bool:
    return bool(TABLE_CAPTION_RE.match(_para_text(node)))


def _context_before_table(
    nodes: list[dict[str, Any]],
    table_index: int,
    *,
    book: Book | None = None,
    max_chars: int = 1200,
) -> str:
    """表格前的正文/标题节选（不单是表内数据）。"""
    parts: list[str] = []
    if book and book.title:
        parts.append(f"书名：{book.title}")
    for j in range(table_index - 1, -1, -1):
        if j < 0:
            break
        n = nodes[j]
        if not isinstance(n, dict):
            continue
        t = n.get("type")
        if t == "heading":
            text = _inline_to_markdown(n.get("content")).strip()
            if text:
                parts.insert(0, f"[标题] {text}")
        elif t == "paragraph":
            text = _para_text(n)
            if text and not _is_table_caption_para(n) and not _is_figure_caption_para(n):
                parts.insert(0, text)
        joined = "\n".join(parts)
        if len(joined) >= max_chars:
            break
    return "\n".join(parts)[-max_chars:]


def _context_before_figure(
    nodes: list[dict[str, Any]],
    figure_index: int,
    *,
    book: Book | None = None,
    max_chars: int = 1200,
) -> str:
    parts: list[str] = []
    if book and book.title:
        parts.append(f"书名：{book.title}")
    for j in range(figure_index - 1, -1, -1):
        n = nodes[j]
        if not isinstance(n, dict):
            continue
        t = n.get("type")
        if t == "heading":
            text = _inline_to_markdown(n.get("content")).strip()
            if text:
                parts.insert(0, f"[标题] {text}")
        elif t == "paragraph":
            text = _para_text(n)
            if text and not _is_table_caption_para(n) and not _is_figure_caption_para(n):
                parts.insert(0, text)
        joined = "\n".join(parts)
        if len(joined) >= max_chars:
            break
    return "\n".join(parts)[-max_chars:]


def apply_overview_caption_edits(
    tiptap_json: dict[str, Any],
    items: list[dict[str, Any]],
    chapter_index: int,
) -> dict[str, Any]:
    """按总览项更新正文中的表题/图题段落。"""
    if not isinstance(tiptap_json, dict) or tiptap_json.get("type") != "doc":
        return tiptap_json
    by_key = {
        (str(it.get("kind")), int(it.get("seq", 0))): str(it.get("title") or "").strip()
        for it in items
    }
    nodes = copy.deepcopy(list(tiptap_json.get("content") or []))
    fig_seq = 0
    tbl_seq = 0

    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        ntype = node.get("type")
        if ntype == "figureBlock":
            fig_seq += 1
            num = f"{chapter_index}-{fig_seq}"
            title = by_key.get(("figure", fig_seq))
            if title:
                attrs = dict(node.get("attrs") or {})
                attrs["caption"] = title
                nodes[i] = {**node, "attrs": attrs}
                if i + 1 < len(nodes) and _is_figure_caption_para(nodes[i + 1]):
                    nodes[i + 1] = _make_para(f"图{num}：{title}", center=True)
        elif ntype == "table":
            tbl_seq += 1
            num = f"{chapter_index}-{tbl_seq}"
            title = by_key.get(("table", tbl_seq))
            if title and i > 0 and _is_table_caption_para(nodes[i - 1]):
                nodes[i - 1] = _make_para(f"表{num}：{title}", center=True)

    return {"type": "doc", "content": nodes}


def normalize_chapter_figures_tables(
    book_id: UUID,
    chapter_index: int,
    tiptap_json: dict[str, Any] | None,
    db: Session,
    *,
    book: Book | None = None,
) -> dict[str, Any]:
    """规范化本章 TipTap：图表重编号、补引用与居中题注。返回 tiptap_json / text / overview。"""
    if not isinstance(tiptap_json, dict) or tiptap_json.get("type") != "doc":
        return {"tiptap_json": tiptap_json or {"type": "doc", "content": []}, "text": "", "overview": []}

    nodes = list(tiptap_json.get("content") or [])
    out: list[dict[str, Any]] = []
    overview: list[dict[str, Any]] = []
    fig_seq = 0
    tbl_seq = 0
    skip_until = -1

    chapter_figures = get_chapter_figures(book_id, chapter_index, db)
    figures_by_id: dict[str, Figure] = {str(f.id): f for f in chapter_figures}
    used_figure_ids: set[UUID] = set()

    for i, node in enumerate(nodes):
        if i <= skip_until:
            continue
        if not isinstance(node, dict):
            out.append(node)
            continue

        ntype = node.get("type")

        if ntype == "figureBlock":
            fig_seq += 1
            num = f"{chapter_index}-{fig_seq}"
            attrs = dict(node.get("attrs") or {})
            fig_row, attrs = resolve_figure_for_block(
                book_id,
                chapter_index,
                attrs,
                db=db,
                figures_by_id=figures_by_id,
                existing=chapter_figures,
                used=used_figure_ids,
            )
            fig_id = str(attrs.get("figureId") or "")
            db_raw = str((fig_row.raw_annotation if fig_row else "") or "").strip()
            db_caption = str((fig_row.caption if fig_row else "") or "").strip()
            attr_caption = str(attrs.get("caption") or "").strip()
            raw_ann = str(attrs.get("rawAnnotation") or db_raw or "").strip()

            next_node = nodes[i + 1] if i + 1 < len(nodes) else None
            cap_title = ""
            if _is_figure_caption_para(next_node):
                m = FIGURE_CAPTION_RE.match(_para_text(next_node))
                cap_title = _usable_caption_title(m.group(3).strip() if m else "", kind="figure")
                skip_until = i + 1
            else:
                cap_title = _usable_caption_title(attr_caption, kind="figure")
            if not cap_title:
                for candidate in (raw_ann, db_raw, db_caption, attr_caption):
                    cap_title = _caption_from_source(candidate, kind="figure")
                    if cap_title:
                        break
            if not cap_title and book:
                source = _first_specific_text(raw_ann, db_raw, db_caption, attr_caption)
                if source:
                    cap_title = suggest_figure_caption(
                        source,
                        book=book,
                        context=_context_before_figure(nodes, i, book=book),
                        fallback=_figure_caption_fallback(attrs),
                        db=db,
                    )
            if not cap_title:
                cap_title = _figure_caption_fallback(attrs)

            has_ref = False
            if out and out[-1].get("type") == "paragraph":
                prev_text = _para_text(out[-1])
                if prev_text and not _is_figure_caption_para(out[-1]) and not _is_table_caption_para(out[-1]):
                    has_ref = True
                    out[-1] = _patch_para_text(out[-1], _replace_figure_ref(prev_text, chapter_index, fig_seq))
            if not has_ref:
                out.append(_make_para(f"如图{chapter_index}-{fig_seq}所示。"))

            attrs["figureNumber"] = num
            attrs["caption"] = cap_title
            if raw_ann:
                attrs["rawAnnotation"] = raw_ann
            out.append({**node, "attrs": attrs})

            cap_line = f"图{num}：{cap_title}"
            out.append(_make_para(cap_line, center=True))

            fig_row.figure_number = num
            fig_row.caption = cap_title
            fig_row.sort_order = fig_seq * 1000

            overview.append(
                {
                    "kind": "figure",
                    "seq": fig_seq,
                    "number": num,
                    "label": f"图{num}",
                    "title": cap_title,
                    "has_reference": True,
                    "has_caption": True,
                    "figure_id": fig_id or None,
                    "status": str(attrs.get("status") or (fig_row.status.value if fig_row else "")),
                }
            )
            continue

        if ntype == "table":
            tbl_seq += 1
            num = f"{chapter_index}-{tbl_seq}"
            cap_title = ""
            has_caption = False
            has_ref = False

            if out and _is_table_caption_para(out[-1]):
                m = TABLE_CAPTION_RE.match(_para_text(out[-1]))
                cap_title = _usable_caption_title(m.group(3).strip() if m else "", kind="table")
                if not cap_title and book:
                    cap_title = suggest_table_caption(
                        node,
                        book=book,
                        context=_context_before_table(nodes, i, book=book),
                        db=db,
                    )
                elif not cap_title:
                    cap_title = "本章数据表"
                out[-1] = _make_para(f"表{num}：{cap_title}", center=True)
                has_caption = True
                ref_idx = len(out) - 2
                if ref_idx >= 0 and out[ref_idx].get("type") == "paragraph":
                    prev_text = _para_text(out[ref_idx])
                    if prev_text and not _is_table_caption_para(out[ref_idx]):
                        has_ref = True
                        out[ref_idx] = _patch_para_text(
                            out[ref_idx], _replace_table_ref(prev_text, chapter_index, tbl_seq)
                        )
            else:
                if out and out[-1].get("type") == "paragraph":
                    prev_text = _para_text(out[-1])
                    if prev_text and not _is_figure_caption_para(out[-1]):
                        has_ref = True
                        out[-1] = _patch_para_text(
                            out[-1], _replace_table_ref(prev_text, chapter_index, tbl_seq)
                        )
                if not has_ref:
                    out.append(_make_para(f"见表{chapter_index}-{tbl_seq}。"))
                    has_ref = True
                if book:
                    cap_title = suggest_table_caption(
                        node,
                        book=book,
                        context=_context_before_table(nodes, i, book=book),
                        db=db,
                    )
                else:
                    cap_title = "本章数据表"
                out.append(_make_para(f"表{num}：{cap_title}", center=True))
                has_caption = True

            out.append(copy.deepcopy(node))
            overview.append(
                {
                    "kind": "table",
                    "seq": tbl_seq,
                    "number": num,
                    "label": f"表{num}",
                    "title": cap_title,
                    "has_reference": has_ref,
                    "has_caption": has_caption,
                    "figure_id": None,
                    "status": None,
                }
            )
            continue

        if ntype == "paragraph":
            text = _para_text(node)
            prev = nodes[i - 1] if i > 0 else None
            nxt = nodes[i + 1] if i + 1 < len(nodes) else None
            if isinstance(prev, dict) and prev.get("type") == "figureBlock" and _is_figure_caption_para(node):
                continue
            if isinstance(nxt, dict) and nxt.get("type") == "table" and _is_table_caption_para(node):
                continue

        out.append(copy.deepcopy(node))

    doc = {"type": "doc", "content": out}
    db.commit()
    ensure_figure_blocks_persisted(book_id, chapter_index, doc, db)
    renumber_chapter_figures_from_tiptap(book_id, chapter_index, doc, db)
    for item in overview:
        if item.get("kind") != "figure":
            continue
        num = str(item.get("number") or "")
        for block in _iter_figure_blocks(doc):
            attrs = block.get("attrs") or {}
            if str(attrs.get("figureNumber") or "") == num:
                item["figure_id"] = str(attrs.get("figureId") or "") or None
                item["status"] = str(attrs.get("status") or item.get("status") or "")
                break
    text = tiptap_json_to_markdown(doc).strip()
    return {"tiptap_json": doc, "text": text, "overview": overview}


def _iter_figure_blocks(doc: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "figureBlock":
            blocks.append(node)
            return
        for child in node.get("content") or []:
            walk(child)

    walk(doc)
    return blocks
