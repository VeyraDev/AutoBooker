"""Render BookAst to DOCX with publication styles."""

from __future__ import annotations

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from app.services.publication.book_ast import AstBlock, BookAst
from app.services.publication.publication_styles import (
    BODY_PT,
    BOOK_TITLE_PT,
    CAPTION_PT,
    CHAPTER_TITLE_PT,
    DOC_BODY_FONT,
    FIFTH_TITLE_PT,
    FIRST_LINE_INDENT_PT,
    FOURTH_TITLE_PT,
    SECTION_TITLE_PT,
    SIXTH_TITLE_PT,
    SUBSECTION_TITLE_PT,
)
from app.services.tiptap_convert import (
    _add_code_paragraph,
    _add_inline_to_paragraph,
    append_tiptap_to_document,
    docx_block,
    docx_figure_image_only,
    merge_figure_export_attrs,
)

BLACK = RGBColor(0, 0, 0)


def _set_run_font(run, *, name: str = DOC_BODY_FONT, size_pt: float | None = None) -> None:
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        from docx.oxml import OxmlElement

        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), name)
    if size_pt is not None:
        run.font.size = Pt(size_pt)


def _style_docx_run(run, *, size_pt: float, bold: bool = False) -> None:
    _set_run_font(run, size_pt=size_pt)
    run.bold = bold
    run.font.color.rgb = BLACK


def _init_docx_publication_fonts(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = DOC_BODY_FONT
    normal.font.size = Pt(BODY_PT)
    normal.font.color.rgb = BLACK
    rpr = normal._element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        from docx.oxml import OxmlElement

        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), DOC_BODY_FONT)
    rfonts.set(qn("w:hAnsi"), DOC_BODY_FONT)
    rfonts.set(qn("w:eastAsia"), DOC_BODY_FONT)


def _add_body(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(FIRST_LINE_INDENT_PT)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    _style_docx_run(run, size_pt=BODY_PT)


_HEADING_STYLE = {
    1: (CHAPTER_TITLE_PT, True, WD_ALIGN_PARAGRAPH.CENTER, 12, 8),
    2: (SECTION_TITLE_PT, True, WD_ALIGN_PARAGRAPH.CENTER, 10, 6),
    3: (SUBSECTION_TITLE_PT, True, WD_ALIGN_PARAGRAPH.LEFT, 8, 5),
    4: (FOURTH_TITLE_PT, True, WD_ALIGN_PARAGRAPH.LEFT, 8, 5),
    5: (FIFTH_TITLE_PT, False, WD_ALIGN_PARAGRAPH.LEFT, 6, 4),
    6: (SIXTH_TITLE_PT, False, WD_ALIGN_PARAGRAPH.LEFT, 6, 4),
}


def _heading_level(block: AstBlock, fallback: int) -> int:
    node = block.attrs.get("tiptap_node")
    if isinstance(node, dict):
        raw = (node.get("attrs") or {}).get("level")
        try:
            return max(1, min(6, int(raw)))
        except Exception:
            pass
    return max(1, min(6, block.level or fallback))


def _add_publication_heading(
    doc: Document,
    text: str,
    *,
    level: int,
    node: dict | None = None,
) -> None:
    size_pt, bold, align, space_before, space_after = _HEADING_STYLE.get(level, _HEADING_STYLE[3])
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if isinstance(node, dict) and node.get("content"):
        _add_inline_to_paragraph(p, node.get("content"), size_pt=size_pt)
    else:
        p.add_run(text)
    for r in p.runs:
        _style_docx_run(r, size_pt=size_pt, bold=bold)


def render_ast_to_docx(ast: BookAst) -> bytes:
    doc = Document()
    _init_docx_publication_fonts(doc)
    for block in ast.blocks:
        role = block.role
        if role == "book_title":
            p = doc.add_paragraph(block.text)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                _style_docx_run(r, size_pt=BOOK_TITLE_PT, bold=True)
        elif role == "preface_title":
            _add_publication_heading(doc, block.text, level=1)
        elif role == "chapter_title":
            _add_publication_heading(doc, block.text, level=1)
        elif role in ("section_title", "subsection_title"):
            node = block.attrs.get("tiptap_node")
            _add_publication_heading(
                doc,
                block.text,
                level=_heading_level(block, 2 if role == "section_title" else 3),
                node=node if isinstance(node, dict) else None,
            )
        elif role == "body":
            node = block.attrs.get("tiptap_node")
            if isinstance(node, dict):
                docx_block(doc, node)
            else:
                _add_body(doc, block.text)
        elif role == "figure":
            node = block.attrs.get("tiptap_node")
            if isinstance(node, dict):
                merged_attrs = merge_figure_export_attrs(block.attrs, node.get("attrs"))
                export_node = {**node, "attrs": merged_attrs}
                if not docx_figure_image_only(doc, export_node):
                    p = doc.add_paragraph("【图片待生成】")
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p = doc.add_paragraph(block.text)
                for r in p.runs:
                    _style_docx_run(r, size_pt=CAPTION_PT, bold=True)
        elif role == "figure_caption":
            p = doc.add_paragraph(block.text)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                _style_docx_run(r, size_pt=CAPTION_PT)
        elif role == "table_caption":
            p = doc.add_paragraph(block.text)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                _style_docx_run(r, size_pt=CAPTION_PT, bold=True)
        elif role == "table" and block.attrs.get("table_node"):
            append_tiptap_to_document(doc, {"type": "doc", "content": [block.attrs["table_node"]]})
        elif role == "code":
            node = block.attrs.get("tiptap_node")
            if isinstance(node, dict):
                docx_block(doc, node)
            else:
                _add_code_paragraph(doc, block.text)
        elif role == "list":
            node = block.attrs.get("tiptap_node")
            if isinstance(node, dict):
                docx_block(doc, node)
        elif role == "blockquote":
            node = block.attrs.get("tiptap_node")
            if isinstance(node, dict):
                docx_block(doc, node)
            else:
                p = doc.add_paragraph(block.text)
                p.paragraph_format.left_indent = Pt(18)
                for r in p.runs:
                    _style_docx_run(r, size_pt=BODY_PT)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
