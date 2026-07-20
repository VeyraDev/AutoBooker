"""Build export preview HTML and structured payload for the editor dialog."""

from __future__ import annotations

import html
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.services import book_service
from app.services.export_service import _load_ordered_chapters
from app.services.publication.book_ast import AstBlock
from app.services.publication.cover_background import cover_png_data_url
from app.services.publication.export_assembler import build_book_export_ast
from app.services.publication.export_ast import BookExportAst, CoverSection, TocEntry
from app.services.publication.page_formats import (
    get_page_format_from_publication,
    list_page_formats,
)
from app.services.publication.publication_info import normalize_publication_info
from app.services.publication.publication_styles import type_scale_for_format
from app.services.tiptap_convert import _inline_to_markdown


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _block_to_preview_html(block: AstBlock) -> str:
    role = block.role
    text = (block.text or "").strip()
    node = block.attrs.get("tiptap_node")
    if role == "chapter_flyleaf":
        summary = str(block.attrs.get("summary") or "").strip()
        bits = ['<div class="flyleaf-block" data-flyleaf="chapter">', f"<h1>{_esc(text)}</h1>"]
        if summary:
            bits.append(f'<p class="flyleaf-summary">{_esc(summary)}</p>')
        bits.append("</div>")
        return "\n".join(bits)
    if role == "section_flyleaf":
        # 兼容旧数据：按节标题处理，不独占页
        return f"<h2>{_esc(text)}</h2>"
    if role == "body":
        if isinstance(node, dict):
            inner = _inline_to_markdown(node.get("content"))
            return f"<p>{_esc(inner)}</p>" if inner.strip() else ""
        return f"<p>{_esc(text)}</p>" if text else ""
    if role == "section_title":
        return f"<h2>{_esc(text)}</h2>"
    if role == "subsection_title":
        return f"<h3>{_esc(text)}</h3>"
    if role in ("figure_caption", "table_caption"):
        return f"<p class='caption'>{_esc(text)}</p>"
    if role == "figure":
        return f"<p class='figure-placeholder'>【图】{_esc(text)}</p>"
    if role == "code":
        return f"<pre><code>{_esc(text)}</code></pre>"
    if role == "blockquote":
        return f"<blockquote>{_esc(text)}</blockquote>"
    if role == "list" and isinstance(node, dict):
        return f"<p>{_esc(_inline_to_markdown(node.get('content')))}</p>"
    return f"<p>{_esc(text)}</p>" if text else ""


def _colophon_html(pub: dict[str, Any]) -> str:
    title = pub.get("title") or "未命名"
    subtitle = pub.get("subtitle") or ""
    author = pub.get("author") or ""
    publisher = pub.get("publisher") or ""
    year = pub.get("publish_year") or ""
    edition = pub.get("edition") or "第1版"
    isbn = pub.get("isbn") or ""
    cip = pub.get("cip_text") or ""
    price = pub.get("price") or ""
    editor = pub.get("editor") or ""
    proofreader = pub.get("proofreader") or ""
    address = pub.get("address") or ""
    postal = pub.get("postal_code") or ""
    print_count = pub.get("print_count") or ""
    words = pub.get("word_count_label") or ""
    spec = get_page_format_from_publication(pub)
    fmt = pub.get("format_label") or spec.short_label
    size_note = f"{fmt}（{spec.width_mm:.0f}×{spec.height_mm:.0f}mm）"

    parts = [
        f'<section class="export-page export-colophon" data-section="colophon">',
        '<div class="colophon-body">',
    ]
    if cip:
        parts.append('<p class="cip-label"><strong>图书在版编目（CIP）数据</strong></p>')
        parts.append(f'<div class="cip" data-field="cip_text">{_esc(cip)}</div>')
    rows = [
        ("书　　名", title, "title"),
        ("副 书 名", subtitle, "subtitle"),
        ("著　　者", f"{author}　著" if author else "（待填）", "author"),
        ("责任编辑", editor or "（待填）", "editor"),
        ("责任校对", proofreader, "proofreader"),
        ("出版发行", publisher or "（待填）", "publisher"),
        ("地　　址", address, "address"),
        ("邮政编码", postal, "postal_code"),
        ("开　　本", size_note, "format_label"),
        ("字　　数", words, "word_count_label"),
        ("版　　次", f"{year}年　{edition}".strip() if year else edition, "edition"),
        ("印　　数", print_count, "print_count"),
        ("定　　价", price, "price"),
        ("ISBN", isbn, "isbn"),
    ]
    for label, value, field in rows:
        if not value:
            continue
        parts.append(
            f'<p class="colophon-row"><span class="k">{label}</span>'
            f'<span data-field="{field}">{_esc(value)}</span></p>'
        )
    parts.extend(["</div>", "</section>"])
    return "\n".join(parts)


def _cover_html(pub: dict[str, Any], *, db: Session | None = None, book_id: UUID | None = None) -> str:
    data_url = cover_png_data_url(pub, fallback_title=pub.get("title"), db=db, book_id=book_id)
    return (
        f'<section class="export-page export-cover" data-section="cover">'
        f'<img class="cover-raster" src="{data_url}" alt="封面" />'
        f"</section>\n"
        f"{_colophon_html(pub)}"
    )


def _toc_html(entries: list[TocEntry]) -> str:
    from app.services.publication.publication_styles import BODY_PT, PDF_CONTENT_WIDTH_PT
    from app.services.publication.toc_format import toc_entry_plain_line

    lines = [
        '<section class="export-page export-toc" data-section="toc">',
        "<h1>目录</h1>",
        '<div class="toc-list">',
    ]
    cw = float(PDF_CONTENT_WIDTH_PT)
    font_size = float(BODY_PT)
    for entry in entries:
        level = 1 if entry.level <= 1 else 2
        indent_pt = 12.0 if level > 1 else 0.0
        left, page_field = toc_entry_plain_line(
            entry.title or "",
            entry.page,
            content_width_pt=cw,
            font_size_pt=font_size,
            indent_pt=indent_pt,
        )
        pad = f"padding-left:{indent_pt:.0f}pt;" if indent_pt else ""
        line = f"{left}{page_field}" if page_field else left
        lines.append(
            f'<p class="toc-line toc-level-{level}" '
            f'style="margin:6px 0;{pad}white-space:nowrap;font-size:{font_size}pt;'
            f'text-indent:0;">{_esc(line)}</p>'
        )
    lines.extend(["</div>", "</section>"])
    return "\n".join(lines)


def _preview_css(
    width_mm: float,
    height_mm: float,
    *,
    body_pt: float | None = None,
    margin_top_mm: float = 22.0,
    margin_bottom_mm: float = 20.0,
    margin_inner_mm: float = 22.0,
    margin_outer_mm: float = 18.0,
) -> str:
    from app.services.publication.publication_styles import (
        HAO_LIU,
        HAO_SAN,
        HAO_SI,
        HAO_WU,
        HAO_XIAOSAN,
        HAO_XIAOSI,
    )

    large = width_mm >= 180
    b = body_pt if body_pt is not None else (HAO_XIAOSI if large else HAO_WU)
    ls = 1.6 if large else 1.5
    return f"""
.export-preview-root {{
  font-family: "宋体","SimSun","Source Han Serif SC","Noto Serif SC",serif;
  color:#111; line-height:{ls};
  display:flex; flex-direction:column; align-items:center; gap:28px;
  padding:8px 8px 40px;
}}
.export-page {{
  width: min(100%, 420px);
  aspect-ratio: {width_mm} / {height_mm};
  background:#fff;
  box-shadow: 0 8px 28px rgba(15,23,42,.12);
  border:1px solid #e7e5e0;
  box-sizing:border-box;
  overflow:hidden;
  position:relative;
}}
.export-cover {{ padding:0; }}
.cover-raster {{ width:100%; height:100%; object-fit:cover; display:block; }}
.export-colophon {{
  display:flex; flex-direction:column; justify-content:flex-end;
  padding:18px 22px 28px; font-size:{b - 0.5}pt;
}}
.colophon-body {{ border-top:1px solid #ddd; padding-top:14px; }}
.colophon-row {{ margin:3px 0; text-indent:0 !important; }}
.colophon-row .k {{ display:inline-block; min-width:4.5em; color:#333; }}
.cip-label {{ margin:0 0 6px; text-indent:0 !important; }}
.cip {{ white-space:pre-wrap; margin:0 0 12px; font-size:{HAO_LIU}pt; color:#333; text-indent:0 !important; }}
.export-toc, .export-preface, .export-chapter, .export-bibliography {{
  aspect-ratio: auto;
  min-height: 0;
  height: auto;
  padding: 28px 26px 36px;
  overflow: visible;
}}
.export-toc h1, .export-preface > h1, .export-bibliography > h1 {{
  text-align:center; font-size:{HAO_SAN}pt; font-family:"黑体","SimHei",sans-serif; margin:0 0 14px; font-weight:700;
}}
.flyleaf-block {{
  display:flex; flex-direction:column; justify-content:center; align-items:center;
  text-align:center; min-height: 70%; padding: 48px 20px; box-sizing:border-box;
  width:100%;
}}
.flyleaf-block[data-flyleaf="chapter"] h1 {{
  font-family:"黑体","SimHei",sans-serif; font-size:{HAO_SAN}pt; margin:0 0 18px; font-weight:700;
}}
.flyleaf-block[data-flyleaf="section"] h2 {{
  font-family:"黑体","SimHei",sans-serif; font-size:{HAO_XIAOSAN}pt; margin:0; font-weight:700; text-align:center;
}}
.flyleaf-summary {{
  font-family:"楷体","KaiTi",serif; font-size:{b}pt; max-width:85%; line-height:1.7;
  text-indent:0 !important; margin:0; color:#333;
}}
.toc-row {{
  width: 100% !important;
  border-collapse: collapse !important;
  table-layout: fixed !important;
  margin: 6px 0 !important;
  font-size: {HAO_WU}pt;
  text-indent: 0 !important;
}}
.toc-title {{ white-space: nowrap; vertical-align: bottom; }}
.toc-leader {{
  border-bottom: 1px dotted #666 !important;
  vertical-align: bottom !important;
  line-height: 1 !important;
}}
.toc-page {{
  text-align: right !important;
  white-space: nowrap !important;
  vertical-align: bottom !important;
  font-variant-numeric: tabular-nums;
}}
.export-preview-root h2 {{ font-family:"黑体","SimHei",sans-serif; font-size:{HAO_XIAOSAN}pt; text-align:left; margin:14px 0 8px; }}
.export-preview-root h3 {{ font-family:"黑体","SimHei",sans-serif; font-size:{HAO_SI}pt; margin:12px 0 6px; }}
.export-preview-root p {{
  font-family:"宋体","SimSun",serif; text-indent:2em; margin:0; font-size:{b}pt; line-height:{ls};
}}
.export-preview-root .caption, .figure-placeholder {{ text-indent:0; text-align:center; font-size:{HAO_LIU}pt; color:#444; }}
.export-preview-root pre {{ text-indent:0; background:#f5f5f5; padding:10px 12px; overflow:auto; font-size:{HAO_LIU}pt; }}
.export-preview-root blockquote {{
  font-family:"楷体","KaiTi",serif; text-indent:0; margin:8px 2em; color:#444; font-size:{b}pt;
}}
.export-preface p {{ font-family:"楷体","KaiTi",serif; }}
.export-sheet .sheet-inner {{
  padding: 18px 20px 4px !important;
}}
.export-sheet .sheet-footer {{
  display: block !important;
  color: #222 !important;
  text-align: center !important;
  font-size: 10.5pt !important;
}}
""".strip()


def render_export_ast_to_preview_html(
    export_ast: BookExportAst,
    *,
    db: Session | None = None,
    book_id: UUID | None = None,
) -> str:
    pub0: dict[str, Any] = {}
    for section in export_ast.sections:
        if section.type == "cover" and isinstance(section.publication, dict):
            pub0 = section.publication
            break
    spec = get_page_format_from_publication(pub0)
    scale = type_scale_for_format(spec)
    parts: list[str] = [
        f'<div class="export-preview-root"><style>{_preview_css(spec.width_mm, spec.height_mm, body_pt=scale.body_pt, margin_top_mm=spec.margin_top_mm, margin_bottom_mm=spec.margin_bottom_mm, margin_inner_mm=spec.margin_inner_mm, margin_outer_mm=spec.margin_outer_mm)}</style>',
    ]
    for section in export_ast.sections:
        if section.type == "cover":
            pub = section.publication if isinstance(section.publication, dict) else {}
            if not pub:
                pub = {"title": section.title}
            parts.append(_cover_html(pub, db=db, book_id=book_id))
        elif section.type == "toc":
            parts.append(_toc_html(section.entries))
        elif section.type == "preface":
            parts.append('<section class="export-page export-preface" data-section="preface">')
            parts.append(f"<h1>{_esc(section.title)}</h1>")
            for block in section.blocks:
                chunk = _block_to_preview_html(block)
                if chunk:
                    parts.append(chunk)
            parts.append("</section>")
        elif section.type == "chapter":
            parts.append(
                f'<section class="export-page export-chapter" data-section="chapter" data-index="{section.chapter_index}">'
            )
            summary = (getattr(section, "summary", None) or "").strip()
            parts.append('<div class="flyleaf-block" data-flyleaf="chapter">')
            parts.append(f"<h1>{_esc(section.title)}</h1>")
            if summary:
                parts.append(f'<p class="flyleaf-summary">{_esc(summary)}</p>')
            parts.append("</div>")
            for block in section.blocks:
                chunk = _block_to_preview_html(block)
                if chunk:
                    parts.append(chunk)
            parts.append("</section>")
        elif section.type == "bibliography":
            parts.append('<section class="export-page export-bibliography" data-section="bibliography">')
            parts.append(f"<h1>{_esc(section.title)}</h1>")
            for block in section.blocks:
                chunk = _block_to_preview_html(block)
                if chunk:
                    parts.append(chunk)
            parts.append("</section>")
    parts.append("</div>")
    return "\n".join(parts)


def build_export_preview(
    book_id: UUID,
    user: User,
    db: Session,
    *,
    publication_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    book = book_service.get_book_or_404(book_id, user, db)
    from app.services.citation_service import sync_book_bibliography
    from app.services.preface_service import get_preface

    sync_book_bibliography(db, book)
    chapters = _load_ordered_chapters(book_id, db)
    export_ast = build_book_export_ast(
        book,
        chapters,
        db,
        publication_info=publication_info,
    )
    pub: dict[str, Any] = {}
    for section in export_ast.sections:
        if isinstance(section, CoverSection) and section.publication:
            pub = dict(section.publication)
            break
    if not pub:
        pub = normalize_publication_info(
            publication_info if publication_info is not None else getattr(book, "publication_info", None),
            fallback_title=book.title,
        )

    pf = get_preface(book)
    preface_enabled = bool(pf.get("enabled") and isinstance(pf.get("tiptap_json"), dict))
    preface_html = ""
    bib_title = None
    bib_html = ""
    chapter_payload: list[dict[str, Any]] = []
    for section in export_ast.sections:
        if section.type == "preface":
            preface_html = "".join(_block_to_preview_html(b) for b in section.blocks)
        elif section.type == "chapter":
            chapter_payload.append(
                {
                    "index": section.chapter_index,
                    "title": section.title,
                    "html": "".join(_block_to_preview_html(b) for b in section.blocks),
                }
            )
        elif section.type == "bibliography":
            bib_title = section.title
            bib_html = "".join(_block_to_preview_html(b) for b in section.blocks)

    toc = [
        {
            "title": e.title,
            "section_type": e.section_type,
            "chapter_index": e.chapter_index,
            "level": e.level,
            "page": e.page,
        }
        for e in export_ast.toc_entries
    ]

    spec = get_page_format_from_publication(pub)
    return {
        "publication_info": pub,
        "preface_enabled": preface_enabled,
        "preface_title": "前言",
        "preface_html": preface_html,
        "toc": toc,
        "chapters": chapter_payload,
        "bibliography_title": bib_title,
        "bibliography_html": bib_html,
        "preview_html": render_export_ast_to_preview_html(export_ast, db=db, book_id=book.id),
        "cover_image_data_url": cover_png_data_url(
            pub,
            fallback_title=book.title,
            db=db,
            book_id=book.id,
        ),
        "page_format": {
            "id": spec.id,
            "label": spec.label,
            "short_label": spec.short_label,
            "width_mm": spec.width_mm,
            "height_mm": spec.height_mm,
            "margin_top_mm": spec.margin_top_mm,
            "margin_bottom_mm": spec.margin_bottom_mm,
            "margin_inner_mm": spec.margin_inner_mm,
            "margin_outer_mm": spec.margin_outer_mm,
            "type_area_width_mm": round(spec.type_area_width_mm, 1),
            "type_area_height_mm": round(spec.type_area_height_mm, 1),
            "hint": spec.hint,
            "aka": spec.aka,
            "margins_text": (
                f"上{spec.margin_top_mm:.0f}/下{spec.margin_bottom_mm:.0f}/"
                f"内{spec.margin_inner_mm:.0f}/外{spec.margin_outer_mm:.0f}mm"
            ),
            "binding_type": pub.get("binding_type") or "paperback",
        },
        "page_format_options": list_page_formats(binding=pub.get("binding_type")),
    }
