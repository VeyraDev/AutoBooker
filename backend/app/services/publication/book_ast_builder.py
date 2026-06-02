"""Build BookAst from Book + chapters + preface."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.models.figure import Figure
from app.services.preface_service import get_preface
from app.services.publication.book_ast import AstBlock, BookAst
from app.services.tiptap_convert import _inline_to_markdown

TABLE_CAPTION_RE = re.compile(r"^表\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]\s*(.+)$")
FIGURE_CAPTION_RE = re.compile(r"^图\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]\s*(.+)$")


def export_chapter_title(ch: Chapter) -> str:
    """导出章标题：书名大纲里已含「第X章」，不再加「第 N 章　」前缀。"""
    title = (ch.title or "").strip()
    return title or f"第{ch.index}章"


def _heading_role(level: int) -> str:
    if level <= 1:
        return "section_title"
    if level == 2:
        return "section_title"
    return "subsection_title"


def _looks_like_flat_table_line(text: str) -> bool:
    return "\t" in text and text.count("\t") >= 1


def _walk_tiptap(
    nodes: list[dict[str, Any]],
    blocks: list[AstBlock],
    *,
    chapter_index: int,
    table_counter: list[int],
    figure_by_id: dict[str, Figure],
) -> None:
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        t = node.get("type")
        if t == "heading":
            level = int((node.get("attrs") or {}).get("level") or 2)
            text = _inline_to_markdown(node.get("content"))
            blocks.append(
                AstBlock(
                    role=_heading_role(level),
                    text=text,
                    level=level,
                    attrs={"tiptap_node": node},
                )
            )
        elif t == "paragraph":
            text = _inline_to_markdown(node.get("content"))
            if text.strip():
                prev = nodes[i - 1] if i > 0 else None
                if (
                    isinstance(prev, dict)
                    and prev.get("type") == "figureBlock"
                    and FIGURE_CAPTION_RE.match(text.strip())
                ):
                    continue
                nxt = nodes[i + 1] if i + 1 < len(nodes) else None
                if (
                    isinstance(nxt, dict)
                    and nxt.get("type") == "table"
                    and _looks_like_flat_table_line(text)
                ):
                    continue
                if isinstance(nxt, dict) and nxt.get("type") == "table" and TABLE_CAPTION_RE.match(
                    text.strip()
                ):
                    continue
                blocks.append(AstBlock(role="body", text=text, attrs={"tiptap_node": node}))
        elif t == "blockquote":
            blocks.append(AstBlock(role="blockquote", text="", attrs={"tiptap_node": node}))
        elif t == "codeBlock":
            blocks.append(
                AstBlock(
                    role="code",
                    text=_inline_to_markdown(node.get("content")),
                    attrs={"tiptap_node": node},
                )
            )
        elif t == "table":
            table_counter[0] += 1
            num = f"{chapter_index}-{table_counter[0]}"
            prev = nodes[i - 1] if i > 0 else None
            caption_text = f"表 {num}"
            if isinstance(prev, dict) and prev.get("type") == "paragraph":
                prev_text = _inline_to_markdown(prev.get("content")).strip()
                m = TABLE_CAPTION_RE.match(prev_text)
                if m:
                    caption_text = prev_text
            blocks.append(
                AstBlock(role="table_caption", text=caption_text, attrs={"table_number": num})
            )
            blocks.append(AstBlock(role="table", text="[table]", attrs={"table_node": node}))
        elif t == "figureBlock":
            attrs = dict(node.get("attrs") or {})
            fid = str(attrs.get("figureId") or "")
            fig = figure_by_id.get(fid)
            num = str(attrs.get("figureNumber") or (fig.figure_number if fig else "") or "").strip()
            cap = str(attrs.get("caption") or attrs.get("rawAnnotation") or "").strip()
            label = f"图 {num}" if num else "图"
            if fig and fig.file_url and not attrs.get("fileUrl"):
                attrs["fileUrl"] = fig.file_url
            node_for_export = {**node, "attrs": {**(node.get("attrs") or {}), **attrs}}
            blocks.append(
                AstBlock(role="figure", text=label, attrs={**attrs, "tiptap_node": node_for_export})
            )
            cap_line = ""
            nxt = nodes[i + 1] if i + 1 < len(nodes) else None
            if isinstance(nxt, dict) and nxt.get("type") == "paragraph":
                nxt_text = _inline_to_markdown(nxt.get("content")).strip()
                m = FIGURE_CAPTION_RE.match(nxt_text)
                if m:
                    cap_line = nxt_text
            if not cap_line and cap:
                cap_line = f"图{num}：{cap}" if num else cap
            if cap_line:
                blocks.append(AstBlock(role="figure_caption", text=cap_line[:200]))
        elif t in ("bulletList", "orderedList"):
            blocks.append(AstBlock(role="list", text=t, attrs={"tiptap_node": node}))
        # 不再对 table / list / figure 等子树做通用递归，避免表格单元格被重复导出为正文


def build_book_ast(book: Book, chapters: list[Chapter], db: Session) -> BookAst:
    ast = BookAst(title=book.title or "未命名")
    ast.blocks.append(AstBlock(role="book_title", text=book.title or "未命名"))

    pf = get_preface(book)
    if pf.get("enabled") and isinstance(pf.get("tiptap_json"), dict):
        ast.blocks.append(AstBlock(role="preface_title", text="前言"))
        tj = pf["tiptap_json"]
        _walk_tiptap(
            tj.get("content") or [],
            ast.blocks,
            chapter_index=0,
            table_counter=[0],
            figure_by_id={},
        )

    figures = db.query(Figure).filter(Figure.book_id == book.id).all()
    figure_by_id = {str(f.id): f for f in figures}

    for ch in chapters:
        ast.blocks.append(
            AstBlock(
                role="chapter_title",
                text=export_chapter_title(ch),
                attrs={"chapter_index": ch.index},
            )
        )
        meta = ch.content if isinstance(ch.content, dict) else {}
        tj = meta.get("tiptap_json")
        if isinstance(tj, dict):
            _walk_tiptap(
                tj.get("content") or [],
                ast.blocks,
                chapter_index=ch.index,
                table_counter=[0],
                figure_by_id=figure_by_id,
            )
        elif meta.get("text"):
            ast.blocks.append(AstBlock(role="body", text=str(meta.get("text"))[:50000]))

    return ast
