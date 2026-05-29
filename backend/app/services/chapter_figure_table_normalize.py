"""本章图表与表格一键排序：重编号、补引用与题注。"""

from __future__ import annotations

import copy
import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.services.figure_service import (
    get_chapter_figures,
    renumber_chapter_figures_from_tiptap,
)
from app.services.table_caption_ai import suggest_table_caption
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


def _table_title_from_node(table: dict[str, Any]) -> str:
    rows = [
        r
        for r in (table.get("content") or [])
        if isinstance(r, dict) and r.get("type") == "tableRow"
    ]
    if not rows:
        return "附表"
    first = rows[0]
    cells = [
        c
        for c in (first.get("content") or [])
        if isinstance(c, dict) and c.get("type") in ("tableCell", "tableHeader")
    ]
    headers: list[str] = []
    for cell in cells:
        for sub in cell.get("content") or []:
            if isinstance(sub, dict) and sub.get("type") == "paragraph":
                t = _inline_to_markdown(sub.get("content")).strip()
                if t:
                    headers.append(t)
    if headers:
        return "、".join(headers[:3])[:48]
    return "附表"


def _make_para(text: str, *, center: bool = False) -> dict[str, Any]:
    node: dict[str, Any] = {
        "type": "paragraph",
        "content": [{"type": "text", "text": text}],
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
    out["content"] = [{"type": "text", "text": new_text}]
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


def _context_from_out(out: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for n in out[-5:]:
        if not isinstance(n, dict) or n.get("type") != "paragraph":
            continue
        t = _para_text(n)
        if t and not _is_table_caption_para(n) and not _is_figure_caption_para(n):
            texts.append(t)
    return "\n".join(texts)


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

    figures_by_id = {str(f.id): f for f in get_chapter_figures(book_id, chapter_index, db)}

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
            fig_id = str(attrs.get("figureId") or "")
            raw_ann = str(attrs.get("rawAnnotation") or attrs.get("caption") or "").strip()

            next_node = nodes[i + 1] if i + 1 < len(nodes) else None
            cap_title = ""
            if _is_figure_caption_para(next_node):
                m = FIGURE_CAPTION_RE.match(_para_text(next_node))
                cap_title = (m.group(3).strip() if m else "") or _short_title(raw_ann)
                skip_until = i + 1
            else:
                cap_title = _short_title(str(attrs.get("caption") or raw_ann))

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

            fig_row = figures_by_id.get(fig_id)
            if fig_row:
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
                cap_title = (m.group(3).strip() if m else "") or ""
                if not cap_title and book:
                    cap_title = suggest_table_caption(
                        node,
                        book=book,
                        context=_context_from_out(out),
                    )
                elif not cap_title:
                    cap_title = "附表"
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
                        context=_context_from_out(out),
                    )
                else:
                    cap_title = "附表"
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
    renumber_chapter_figures_from_tiptap(book_id, chapter_index, doc, db)
    text = tiptap_json_to_markdown(doc).strip()
    return {"tiptap_json": doc, "text": text, "overview": overview}
