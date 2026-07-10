"""Render BookAst to PDF via HTML + PyMuPDF Story."""

from __future__ import annotations

import html
import io
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.services.publication.book_ast import BookAst
from app.services.publication.export_ast import BookExportAst
from app.services.publication.book_ast import AstBlock
from app.services.publication.page_numbers import add_pdf_page_numbers
from app.services.publication.publication_styles import (
    PDF_CONTENT_HEIGHT_PT,
    PDF_CONTENT_WIDTH_PT,
    PDF_FIGURE_MAX_HEIGHT_PX,
    PDF_FIGURE_WIDTH_PX,
    PDF_PAGE_MARGIN_PT,
    PUBLICATION_CSS,
)
from app.services.tiptap_convert import (
    _inline_to_markdown,
    _materialize_figure_local_path,
    _materialize_figure_raster_for_export,
    _table_cell_inline_nodes,
    merge_figure_export_attrs,
)


def _trim_figure_margins(img: Image.Image, *, pad: int = 10) -> Image.Image:
    """裁掉流程图/截图四周留白，避免导出后图形在页面上显得过小。"""
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = bg.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")
    bbox = ImageOps.invert(img).getbbox()
    if not bbox:
        return img
    left, top, right, bottom = bbox
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(img.width, right + pad)
    bottom = min(img.height, bottom + pad)
    return img.crop((left, top, right, bottom))


def _figure_image_for_pdf(local: Path) -> tuple[bytes, int, int]:
    """裁边并缩放到正文栏宽，返回 (png_bytes, width_px, height_px)。"""
    target_w = PDF_FIGURE_WIDTH_PX
    max_h = PDF_FIGURE_MAX_HEIGHT_PX
    with Image.open(local) as raw:
        img = _trim_figure_margins(raw)
        rgba = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        if rgba:
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")
        w, h = img.size
        if w <= 0 or h <= 0:
            raise ValueError("invalid image size")
        target_h = max(1, round(h * target_w / w))
        if target_h > max_h:
            target_h = max_h
        resample = getattr(Image, "Resampling", Image).LANCZOS
        img = img.resize((target_w, target_h), resample)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), target_w, target_h


def _figure_img_html(archive_name: str, width_px: int, height_px: int) -> str:
    return (
        f"<p style='text-align:center;margin:0;'>"
        f"<img width='{width_px}' height='{height_px}' "
        f"style='width:{width_px}px;height:{height_px}px;border:none;' "
        f"src='{archive_name}'/>"
        f"</p>"
    )


def _prepare_figure_archive_entry(
    attrs: dict[str, Any],
    fig_idx: int,
    archive: fitz.Archive,
    db: Session | None = None,
) -> tuple[str, int, int] | None:
    with _materialize_figure_local_path(attrs, db=db) as local:
        if not local:
            return None
        with _materialize_figure_raster_for_export(local) as raster:
            if not raster:
                return None
            name = f"figure-{fig_idx}.png"
            try:
                png_bytes, width_px, height_px = _figure_image_for_pdf(raster)
            except Exception:
                png_bytes = raster.read_bytes()
                width_px = PDF_FIGURE_WIDTH_PX
                height_px = max(1, width_px * 3 // 4)
            archive.add(png_bytes, name)
            return name, width_px, height_px



def _detect_bad_figure_layout_ids(pdf_bytes: bytes) -> set[str]:
    """检测贴页底被截断或宽度过窄的插图，触发换页重排。"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    margin = PDF_PAGE_MARGIN_PT
    bottom_threshold = 36
    min_width_pt = PDF_CONTENT_WIDTH_PT * 0.72
    bad: set[str] = set()
    fig_idx = 0
    try:
        for page in doc:
            content_bottom = page.rect.height - margin
            rects: list[fitz.Rect] = []
            for im in page.get_images(full=True):
                rects.extend(page.get_image_rects(im[7]))
            rects.sort(key=lambda r: r.y0)
            for rect in rects:
                fig_idx += 1
                clipped = rect.height > 8 and rect.y1 >= content_bottom - bottom_threshold
                too_narrow = rect.width < min_width_pt
                if clipped or too_narrow:
                    bad.add(f"figgrp-{fig_idx}")
    finally:
        doc.close()
    return bad


def _render_story_html_to_pdf(html_doc: str, archive: fitz.Archive | None = None) -> bytes:
    story = fitz.Story(html=html_doc, user_css=PUBLICATION_CSS, archive=archive)
    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    mediabox = fitz.paper_rect("a4")
    margin = PDF_PAGE_MARGIN_PT
    where = mediabox + (margin, margin, -margin, -margin)
    more = 1
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buf.getvalue()


def _repair_undersized_pdf_figures(pdf_bytes: bytes) -> bytes:
    """Story 在页末会把插图压成极小尺寸；用原图流按栏宽重绘。"""
    min_width_pt = PDF_CONTENT_WIDTH_PT * 0.85
    margin = PDF_PAGE_MARGIN_PT
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    repairs: list[tuple[int, fitz.Rect, bytes, int, int]] = []
    try:
        for pi, page in enumerate(doc):
            for im in page.get_images(full=True):
                info = doc.extract_image(im[0])
                stream = info.get("image")
                if not stream:
                    continue
                iw, ih = int(info["width"]), int(info["height"])
                for rect in page.get_image_rects(im[7]):
                    if rect.width >= min_width_pt:
                        continue
                    repairs.append((pi, fitz.Rect(rect), stream, iw, ih))

        for pi, rect, stream, iw, ih in sorted(repairs, key=lambda r: r[0], reverse=True):
            page = doc[pi]
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
            new_w = PDF_CONTENT_WIDTH_PT
            new_h = new_w * (ih / max(iw, 1))
            page_bottom = page.rect.height - margin
            y0 = rect.y0
            target_page = page
            if y0 + new_h > page_bottom:
                target_page = doc.new_page(
                    pi + 1,
                    width=page.rect.width,
                    height=page.rect.height,
                )
                y0 = margin
            new_rect = fitz.Rect(margin, y0, margin + new_w, y0 + new_h)
            target_page.insert_image(new_rect, stream=stream)
    finally:
        out = doc.tobytes()
        doc.close()
    return out


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
        elif t == "citation":
            parts.append(
                f"<span class='citation'>{html.escape(str((node.get('attrs') or {}).get('renderedText') or '（引用）'))}</span>"
            )
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
        tag = f"h{level}"
        cls = "section-title" if level <= 2 else "subsection-title"
        inner = _inline_to_html(node.get("content"))
        return f"<{tag} class='{cls}'>{inner}</{tag}>"
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
        return ""
    return ""


def _build_publication_html(
    ast: BookAst,
    *,
    page_break_figure_ids: set[str],
    archive: fitz.Archive,
    db: Session | None = None,
) -> str:
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
    blocks = ast.blocks
    fig_idx = 0
    i = 0
    while i < len(blocks):
        block = blocks[i]
        role = block.role
        t = _esc(block.text)
        node = block.attrs.get("tiptap_node")

        if role == "figure":
            fig_idx += 1
            fig_id = f"figgrp-{fig_idx}"
            fig_html = ""
            if isinstance(node, dict):
                merged_attrs = merge_figure_export_attrs(block.attrs, node.get("attrs"))
                prepared = _prepare_figure_archive_entry(merged_attrs, fig_idx, archive, db=db)
                if prepared:
                    name, width_px, height_px = prepared
                    fig_html = _figure_img_html(name, width_px, height_px)
            caption_html = ""
            if i + 1 < len(blocks) and blocks[i + 1].role == "figure_caption":
                cap = _esc(blocks[i + 1].text)
                caption_html = f"<p class='caption'>{cap}</p>"
                i += 1
            if fig_html:
                if fig_id in page_break_figure_ids:
                    parts.append("<p style='page-break-before:always;margin:0'></p>")
                parts.append(
                    f"<div class='figure-group' id='{fig_id}'>"
                    f"{fig_html}{caption_html}</div>"
                )
            i += 1
            continue

        if role == "figure_caption":
            i += 1
            continue

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
            if block.attrs.get("force_page_break"):
                parts.append("<p style='page-break-before:always;margin:0'></p>")
                if not t and not isinstance(node, dict):
                    i += 1
                    continue
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
                else:
                    parts.append(f"<p class='body'>{t}</p>")
            else:
                parts.append(f"<p class='body'>{t}</p>")
        elif role == "table_caption":
            parts.append(f"<p class='caption'>{t}</p>")
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
                else:
                    parts.append(f"<pre><code>{t}</code></pre>")
            else:
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
                else:
                    parts.append(f"<blockquote>{t}</blockquote>")
            else:
                parts.append(f"<blockquote>{t}</blockquote>")
        i += 1

    parts.append("</body></html>")
    return "".join(parts)


def _export_ast_to_linear_book_ast(export_ast: BookExportAst) -> BookAst:
    blocks: list[AstBlock] = []

    def append_page_break_once() -> None:
        if not blocks:
            return
        last = blocks[-1]
        if last.role == "body" and last.attrs.get("force_page_break"):
            return
        blocks.append(AstBlock(role="body", text="", attrs={"force_page_break": True}))

    for section in export_ast.sections:
        if section.type == "cover":
            blocks.append(AstBlock(role="book_title", text=section.title))
            if section.page_break_after:
                append_page_break_once()
        elif section.type == "toc":
            if section.page_break_before:
                append_page_break_once()
            blocks.append(AstBlock(role="chapter_title", text="目录"))
            for entry in section.entries:
                blocks.append(AstBlock(role="body", text=entry.title))
            if section.page_break_after:
                append_page_break_once()
        elif section.type == "preface":
            if section.page_break_before:
                append_page_break_once()
            blocks.append(AstBlock(role="preface_title", text=section.title))
            blocks.extend(section.blocks)
            if section.page_break_after:
                append_page_break_once()
        elif section.type == "chapter":
            if section.page_break_before:
                append_page_break_once()
            blocks.append(
                AstBlock(
                    role="chapter_title",
                    text=section.title,
                    attrs={"chapter_index": section.chapter_index},
                )
            )
            blocks.extend(section.blocks)
        elif section.type == "bibliography":
            if section.page_break_before:
                append_page_break_once()
            blocks.append(
                AstBlock(role="chapter_title", text=section.title, attrs={"book_end_matter": True})
            )
            blocks.extend(section.blocks)
    return BookAst(title=export_ast.title, blocks=blocks)


def render_export_ast_to_pdf(export_ast: BookExportAst, db: Session | None = None) -> bytes:
    return render_ast_to_pdf(_export_ast_to_linear_book_ast(export_ast), db=db)


def render_ast_to_pdf(ast: BookAst, db: Session | None = None) -> bytes:
    page_break_ids: set[str] = set()
    pdf_bytes = b""
    for _ in range(4):
        archive = fitz.Archive()
        html_doc = _build_publication_html(ast, page_break_figure_ids=page_break_ids, archive=archive, db=db)
        pdf_bytes = _render_story_html_to_pdf(html_doc, archive)
        bad = _detect_bad_figure_layout_ids(pdf_bytes)
        if not bad - page_break_ids:
            break
        page_break_ids |= bad
    pdf_bytes = _repair_undersized_pdf_figures(pdf_bytes)
    return add_pdf_page_numbers(pdf_bytes)
