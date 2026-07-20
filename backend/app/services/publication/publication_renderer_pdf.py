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


def _render_story_html_to_pdf(
    html_doc: str,
    archive: fitz.Archive | None = None,
    *,
    page_width_pt: float | None = None,
    page_height_pt: float | None = None,
    margin_pt: float | None = None,
    margins_ltrb_pt: tuple[float, float, float, float] | None = None,
    user_css: str | None = None,
) -> bytes:
    from app.services.publication.publication_styles import PAGE_HEIGHT_PT, PAGE_WIDTH_PT, PUBLICATION_CSS

    story = fitz.Story(html=html_doc, user_css=user_css or PUBLICATION_CSS, archive=archive)
    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    w = page_width_pt if page_width_pt is not None else PAGE_WIDTH_PT
    h = page_height_pt if page_height_pt is not None else PAGE_HEIGHT_PT
    mediabox = fitz.Rect(0, 0, w, h)
    if margins_ltrb_pt is not None:
        left, top, right, bottom = margins_ltrb_pt
        where = mediabox + (left, top, -right, -bottom)
    else:
        margin = margin_pt if margin_pt is not None else PDF_PAGE_MARGIN_PT
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


def _full_bleed_cover_first_page(pdf_bytes: bytes) -> bytes:
    """将首页封面图铺满整页（Story 排版带正文边距，封面需出血满版）。"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.page_count < 1:
            return pdf_bytes
        page = doc[0]
        best: tuple[float, bytes] | None = None
        for im in page.get_images(full=True):
            info = doc.extract_image(im[0])
            stream = info.get("image")
            if not stream:
                continue
            for rect in page.get_image_rects(im[7]):
                area = float(rect.width * rect.height)
                if best is None or area > best[0]:
                    best = (area, stream)
        if best is None:
            return pdf_bytes
        stream = best[1]
        rect = fitz.Rect(page.rect)
        # 用新页替换首页，避免旧图与白边残留在内容流中
        new_page = doc.new_page(0, width=rect.width, height=rect.height)
        new_page.insert_image(new_page.rect, stream=stream, keep_proportion=False)
        doc.delete_page(1)
        return doc.tobytes()
    finally:
        doc.close()


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
    content_width_pt: float | None = None,
    content_height_pt: float | None = None,
) -> str:
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
    blocks = ast.blocks
    fig_idx = 0
    i = 0
    page_fresh = True  # 章过渡分页后为 True，避免节标题再插空白页
    while i < len(blocks):
        block = blocks[i]
        role = block.role
        t = _esc(block.text)
        node = block.attrs.get("tiptap_node")

        if role == "figure":
            fig_idx += 1
            fig_id = f"figgrp-{fig_idx}"
            fig_html = ""
            if block.attrs.get("cover_image"):
                from app.services.publication.cover_background import render_cover_png
                from app.services.publication.page_formats import cover_pixel_size, get_page_format_from_publication

                pub = block.attrs.get("publication") if isinstance(block.attrs.get("publication"), dict) else {}
                png = render_cover_png(pub, fallback_title=block.text, db=db)
                name = f"cover-{fig_idx}.png"
                archive.add((png, name))
                spec = get_page_format_from_publication(pub)
                cw, ch = cover_pixel_size(spec)
                use_w = content_width_pt if content_width_pt is not None else PDF_CONTENT_WIDTH_PT
                use_h = content_height_pt if content_height_pt is not None else PDF_CONTENT_HEIGHT_PT
                width_px = int(use_w / 72 * 96)
                height_px = int(width_px * ch / max(1, cw))
                max_h = int(use_h / 72 * 96)
                fig_html = _figure_img_html(name, width_px, min(height_px, max_h))
            elif isinstance(node, dict):
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
                if fig_id in page_break_figure_ids and not block.attrs.get("cover_image"):
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
            page_fresh = False
        elif role == "preface_title":
            parts.append(f"<h1 class='preface-title'>{t}</h1>")
            page_fresh = False
        elif role == "chapter_flyleaf":
            if block.attrs.get("body_start"):
                parts.append("<p id='autobook-body-start' style='margin:0;font-size:1pt;color:#fff'>[[BODY_START]]</p>")
            summary = _esc(str(block.attrs.get("summary") or ""))
            parts.append("<div class='flyleaf'>")
            parts.append(f"<div class='flyleaf-title'>{t}</div>")
            if summary:
                parts.append(f"<p class='flyleaf-summary'>{summary}</p>")
            parts.append("</div>")
            page_fresh = True
        elif role == "toc_entry":
            # 字符点线单行：Story 多列表格会吞页码 / 中间列拉不开
            from app.services.publication.publication_styles import BODY_PT
            from app.services.publication.toc_format import toc_entry_plain_line

            level = int(block.attrs.get("level") or block.level or 1)
            page_raw = block.attrs.get("page")
            try:
                page_num = None if page_raw is None or page_raw == "" else int(page_raw)
            except (TypeError, ValueError):
                page_num = None
            cw = float(content_width_pt) if content_width_pt is not None else float(PDF_CONTENT_WIDTH_PT)
            font_size = float(BODY_PT)
            indent_pt = 12.0 if level > 1 else 0.0
            left, page_field = toc_entry_plain_line(
                block.text or "",
                page_num,
                content_width_pt=cw,
                font_size_pt=font_size,
                indent_pt=indent_pt,
            )
            pad = f"padding-left:{indent_pt:.1f}pt;" if indent_pt else ""
            # 整行同一字体，避免 Courier 槽位被 Story 裁切成末位数字
            line = f"{left}{page_field}" if page_field else left
            parts.append(
                f'<p class="toc-line" style="margin:3pt 0;{pad}white-space:nowrap;'
                f'font-size:{font_size}pt;text-indent:0;">{_esc(line)}</p>'
            )
            page_fresh = False
        elif role == "section_flyleaf":
            if not page_fresh:
                parts.append("<p style='page-break-before:always;margin:0'></p>")
            parts.append(f"<h2 class='section-title'>{t}</h2>")
            page_fresh = False
        elif role == "chapter_title":
            if block.attrs.get("body_start"):
                parts.append("<p id='autobook-body-start' style='margin:0;font-size:1pt;color:#fff'> </p>")
            parts.append(f"<h1 class='chapter-title'>{t}</h1>")
            page_fresh = False
        elif role in ("section_title", "subsection_title"):
            if role == "section_title" and not page_fresh:
                parts.append("<p style='page-break-before:always;margin:0'></p>")
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
                else:
                    parts.append(f"<h2 class='section-title'>{t}</h2>")
            else:
                parts.append(f"<h2 class='section-title'>{t}</h2>")
            page_fresh = False
        elif role == "body":
            if block.attrs.get("force_page_break"):
                parts.append("<p style='page-break-before:always;margin:0'></p>")
                page_fresh = True
                if not t and not isinstance(node, dict):
                    i += 1
                    continue
            if block.attrs.get("colophon_spacer"):
                # 把版权信息顶到页面下半部（对齐预览 flex-end）
                parts.append("<p class='colophon-spacer'>&nbsp;</p>")
                page_fresh = False
                i += 1
                continue
            cls = "body colophon-line" if block.attrs.get("colophon") else "body"
            if block.attrs.get("colophon_first"):
                cls = f"{cls} colophon-first"
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
                else:
                    parts.append(f"<p class='{cls}'>{t}</p>")
            else:
                indent = "text-indent:0;" if block.attrs.get("colophon") or block.attrs.get("cover_meta") else ""
                parts.append(f"<p class='{cls}' style='{indent}'>{t}</p>")
            page_fresh = False
        elif role == "table_caption":
            parts.append(f"<p class='caption'>{t}</p>")
            page_fresh = False
        elif role == "table" and block.attrs.get("table_node"):
            table_node = block.attrs["table_node"]
            if isinstance(table_node, dict):
                chunk = _tiptap_node_to_html(table_node)
                if chunk:
                    parts.append(chunk)
            page_fresh = False
        elif role == "code":
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
                else:
                    parts.append(f"<pre><code>{t}</code></pre>")
            else:
                parts.append(f"<pre><code>{t}</code></pre>")
            page_fresh = False
        elif role == "list":
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
            page_fresh = False
        elif role == "blockquote":
            if isinstance(node, dict):
                chunk = _tiptap_node_to_html(node)
                if chunk:
                    parts.append(chunk)
                else:
                    parts.append(f"<blockquote>{t}</blockquote>")
            else:
                parts.append(f"<blockquote>{t}</blockquote>")
            page_fresh = False
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

    body_started = False
    for section in export_ast.sections:
        if section.type == "cover":
            pub = section.publication if isinstance(getattr(section, "publication", None), dict) else {}
            title = (pub.get("title") or section.title or "").strip() or "未命名"
            blocks.append(
                AstBlock(
                    role="figure",
                    text=title,
                    attrs={"cover_image": True, "publication": pub},
                )
            )
            append_page_break_once()
            # 版权页：字段与导出预览一致；用 spacer 把内容压到下半页
            from app.services.publication.publication_info import build_colophon_lines

            blocks.append(
                AstBlock(role="body", text="", attrs={"colophon_spacer": True})
            )
            for idx, line in enumerate(build_colophon_lines(pub)):
                blocks.append(
                    AstBlock(
                        role="body",
                        text=line,
                        attrs={"colophon": True, "colophon_first": idx == 0},
                    )
                )
            if section.page_break_after:
                append_page_break_once()
        elif section.type == "toc":
            if section.page_break_before:
                append_page_break_once()
            blocks.append(AstBlock(role="chapter_title", text="目录"))
            for entry in section.entries:
                blocks.append(
                    AstBlock(
                        role="toc_entry",
                        text=entry.title,
                        level=getattr(entry, "level", 1) or 1,
                        attrs={
                            "page": entry.page,
                            "level": getattr(entry, "level", 1) or 1,
                        },
                    )
                )
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
            attrs: dict = {
                "chapter_index": section.chapter_index,
                "summary": getattr(section, "summary", "") or "",
            }
            if not body_started:
                attrs["body_start"] = True
                body_started = True
            blocks.append(AstBlock(role="chapter_flyleaf", text=section.title, attrs=attrs))
            append_page_break_once()
            blocks.extend(section.blocks)
        elif section.type == "bibliography":
            if section.page_break_before:
                append_page_break_once()
            if not body_started:
                body_started = True
            blocks.append(
                AstBlock(role="chapter_title", text=section.title, attrs={"book_end_matter": True})
            )
            blocks.extend(section.blocks)
    return BookAst(title=export_ast.title, blocks=blocks)


def _estimate_body_start_page_index(export_ast: BookExportAst) -> int:
    """估算 PDF 中正文起始页（0-based）：封面+版权+目录+前言。"""
    pages = 2  # 封面图 + 版权页
    pages += 1  # 目录至少 1 页
    for section in export_ast.sections:
        if section.type == "toc":
            pages += max(0, (len(section.entries) - 1) // 28)
        elif section.type == "preface":
            chars = sum(len(b.text or "") for b in section.blocks)
            pages += max(1, (chars + 399) // 400)
    return pages


def render_export_ast_to_pdf(export_ast: BookExportAst, db: Session | None = None) -> bytes:
    from app.services.publication.page_formats import get_page_format_from_publication
    from app.services.publication.page_numbers import detect_pdf_body_start_page
    from app.services.publication.publication_styles import publication_css_for_body_pt, type_scale_for_format

    pub = {}
    for section in export_ast.sections:
        if section.type == "cover" and isinstance(getattr(section, "publication", None), dict):
            pub = section.publication
            break
    spec = get_page_format_from_publication(pub)
    estimate = _estimate_body_start_page_index(export_ast)
    chapter_titles = [
        section.title
        for section in export_ast.sections
        if section.type == "chapter" and (section.title or "").strip()
    ]
    pdf_bytes = render_ast_to_pdf(
        _export_ast_to_linear_book_ast(export_ast),
        db=db,
        body_start_page_index=estimate,  # 先占位，最终用检测结果覆盖
        page_width_pt=spec.width_pt,
        page_height_pt=spec.height_pt,
        margins_ltrb_pt=(
            spec.margin_inner_pt,
            spec.margin_top_pt,
            spec.margin_outer_pt,
            spec.margin_bottom_pt,
        ),
        user_css=publication_css_for_body_pt(type_scale_for_format(spec).body_pt),
        content_width_pt=spec.content_width_pt,
        content_height_pt=spec.content_height_pt,
        skip_page_numbers=True,
    )
    body_start = detect_pdf_body_start_page(
        pdf_bytes,
        chapter_titles=chapter_titles,
        fallback=estimate,
    )
    from app.services.publication.page_numbers import add_pdf_page_numbers, scrub_pdf_body_marker

    pdf_bytes = scrub_pdf_body_marker(pdf_bytes)
    return add_pdf_page_numbers(pdf_bytes, body_start_page_index=body_start)


def render_ast_to_pdf(
    ast: BookAst,
    db: Session | None = None,
    *,
    body_start_page_index: int = 0,
    page_width_pt: float | None = None,
    page_height_pt: float | None = None,
    margin_pt: float | None = None,
    margins_ltrb_pt: tuple[float, float, float, float] | None = None,
    user_css: str | None = None,
    content_width_pt: float | None = None,
    content_height_pt: float | None = None,
    skip_page_numbers: bool = False,
) -> bytes:
    page_break_ids: set[str] = set()
    pdf_bytes = b""
    for _ in range(4):
        archive = fitz.Archive()
        html_doc = _build_publication_html(
            ast,
            page_break_figure_ids=page_break_ids,
            archive=archive,
            db=db,
            content_width_pt=content_width_pt,
            content_height_pt=content_height_pt,
        )
        pdf_bytes = _render_story_html_to_pdf(
            html_doc,
            archive,
            page_width_pt=page_width_pt,
            page_height_pt=page_height_pt,
            margin_pt=margin_pt,
            margins_ltrb_pt=margins_ltrb_pt,
            user_css=user_css,
        )
        bad = _detect_bad_figure_layout_ids(pdf_bytes)
        if not bad - page_break_ids:
            break
        page_break_ids |= bad
    pdf_bytes = _repair_undersized_pdf_figures(pdf_bytes)
    has_cover = any(
        b.role == "figure" and b.attrs.get("cover_image") for b in ast.blocks[:5]
    )
    if has_cover:
        pdf_bytes = _full_bleed_cover_first_page(pdf_bytes)
    if skip_page_numbers:
        return pdf_bytes
    return add_pdf_page_numbers(pdf_bytes, body_start_page_index=body_start_page_index)
