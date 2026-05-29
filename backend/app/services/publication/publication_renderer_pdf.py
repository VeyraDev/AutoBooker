"""Render BookAst to PDF via HTML + PyMuPDF Story."""

from __future__ import annotations

import base64
import html
import io
from pathlib import Path
from typing import Any

import fitz

from app.services.publication.book_ast import BookAst
from app.services.publication.publication_styles import PUBLICATION_CSS
from app.services.tiptap_convert import (
    _inline_to_markdown,
    _resolve_figure_local_path,
    _table_cell_inline_nodes,
)


def _figure_img_html(attrs: dict[str, Any]) -> str:
    local = _resolve_figure_local_path(attrs)
    if not local:
        return ""
    ext = local.suffix.lower().lstrip(".") or "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext if ext in ("png", "gif", "webp") else "png"
    b64 = base64.b64encode(local.read_bytes()).decode("ascii")
    return f"<p style='text-align:center;margin:8pt 0'><img src='data:image/{mime};base64,{b64}' style='max-width:100%;height:auto;'/></p>"


def _esc(s: str) -> str:
    return html.escape(s or "").replace("\n", "<br/>")


def _inline_to_html(nodes: list[dict[str, Any]] | None) -> str:
    if not nodes:
        return ""
    parts: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        t = node.get("type")
        if t == "text":
            text = html.escape(str(node.get("text") or ""))
            for m in node.get("marks") or []:
                mt = m.get("type")
                if mt == "bold":
                    text = f"<strong>{text}</strong>"
                elif mt == "italic":
                    text = f"<em>{text}</em>"
                elif mt == "code":
                    text = f"<code>{text}</code>"
            parts.append(text)
        elif t == "hardBreak":
            parts.append("<br/>")
    return "".join(parts)


def _tiptap_node_to_html(node: dict[str, Any]) -> str:
    t = node.get("type")
    if t == "paragraph":
        inner = _inline_to_html(node.get("content"))
        attrs = node.get("attrs") or {}
        if attrs.get("textAlign") == "center":
            return f"<p class='caption'>{inner}</p>" if inner else ""
        return f"<p class='body'>{inner}</p>" if inner else ""
    if t == "heading":
        level = int((node.get("attrs") or {}).get("level") or 2)
        level = max(1, min(6, level))
        tag = "h2" if level <= 2 else "h3"
        inner = _inline_to_html(node.get("content"))
        return f"<{tag} class='section-title'>{inner}</{tag}>"
    if t == "codeBlock":
        code = html.escape(_inline_to_markdown(node.get("content")))
        return f"<pre><code>{code}</code></pre>"
    if t == "blockquote":
        inner_parts: list[str] = []
        for sub in node.get("content") or []:
            if isinstance(sub, dict):
                chunk = _tiptap_node_to_html(sub)
                if chunk:
                    inner_parts.append(chunk)
        return f"<blockquote>{''.join(inner_parts)}</blockquote>"
    if t == "bulletList":
        items: list[str] = []
        for item in node.get("content") or []:
            if not isinstance(item, dict) or item.get("type") != "listItem":
                continue
            li_parts: list[str] = []
            for sub in item.get("content") or []:
                if isinstance(sub, dict):
                    chunk = _tiptap_node_to_html(sub)
                    if chunk:
                        li_parts.append(chunk)
            items.append(f"<li>{''.join(li_parts)}</li>")
        return f"<ul>{''.join(items)}</ul>"
    if t == "orderedList":
        items_o: list[str] = []
        for item in node.get("content") or []:
            if not isinstance(item, dict) or item.get("type") != "listItem":
                continue
            li_parts: list[str] = []
            for sub in item.get("content") or []:
                if isinstance(sub, dict):
                    chunk = _tiptap_node_to_html(sub)
                    if chunk:
                        li_parts.append(chunk)
            items_o.append(f"<li>{''.join(li_parts)}</li>")
        return f"<ol>{''.join(items_o)}</ol>"
    if t == "table":
        rows_html: list[str] = []
        for ri, row in enumerate(node.get("content") or []):
            if not isinstance(row, dict) or row.get("type") != "tableRow":
                continue
            cells = [
                c
                for c in (row.get("content") or [])
                if isinstance(c, dict) and c.get("type") in ("tableCell", "tableHeader")
            ]
            cell_tags: list[str] = []
            for cell in cells:
                tag = "th" if cell.get("type") == "tableHeader" or ri == 0 else "td"
                inline_nodes = _table_cell_inline_nodes(cell)
                text = _inline_to_html(inline_nodes) if inline_nodes else ""
                cell_tags.append(f"<{tag}>{text}</{tag}>")
            rows_html.append(f"<tr>{''.join(cell_tags)}</tr>")
        return f"<table class='export-table'>{''.join(rows_html)}</table>"
    if t == "figureBlock":
        return _figure_img_html(node.get("attrs") or {})
    return ""


def render_ast_to_pdf(ast: BookAst) -> bytes:
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
    for block in ast.blocks:
        role = block.role
        t = _esc(block.text)
        node = block.attrs.get("tiptap_node")
        if role == "book_title":
            parts.append(f"<h1 class='book-title'>{t}</h1>")
        elif role == "preface_title":
            parts.append(f"<h1 class='preface-title'>{t}</h1>")
        elif role == "chapter_title":
            parts.append(f"<h1 class='chapter-title'>{t}</h1>")
        elif role in ("section_title", "subsection_title"):
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
                else:
                    parts.append(f"<h2 class='section-title'>{t}</h2>")
            else:
                parts.append(f"<h2 class='section-title'>{t}</h2>")
        elif role == "body":
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
                    continue
            parts.append(f"<p class='body'>{t}</p>")
        elif role in ("figure_caption", "table_caption"):
            parts.append(f"<p class='caption'>{t}</p>")
        elif role == "figure":
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
                    continue
        elif role == "table" and block.attrs.get("table_node"):
            table_node = block.attrs["table_node"]
            if isinstance(table_node, dict):
                chunk = _tiptap_node_to_html(table_node)
                if chunk:
                    parts.append(chunk)
        elif role == "code":
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
                    continue
            parts.append(f"<pre><code>{t}</code></pre>")
        elif role == "list":
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
        elif role == "blockquote":
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
                    continue
            parts.append(f"<blockquote>{t}</blockquote>")
    parts.append("</body></html>")
    html_doc = "".join(parts)
    story = fitz.Story(html=html_doc, user_css=PUBLICATION_CSS)
    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    mediabox = fitz.paper_rect("a4")
    margin = 56
    where = mediabox + (margin, margin, -margin, -margin)
    more = 1
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buf.getvalue()
