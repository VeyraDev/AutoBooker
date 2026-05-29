"""Render BookAst to DOCX with publication styles."""

from __future__ import annotations

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Pt, RGBColor

from app.services.publication.book_ast import AstBlock, BookAst
from app.services.publication.publication_styles import (
    BODY_PT,
    CAPTION_PT,
    CHAPTER_TITLE_PT,
    FIRST_LINE_INDENT_PT,
    SECTION_TITLE_PT,
)
from app.services.tiptap_convert import append_tiptap_to_document, docx_block, docx_figure_image_only, _add_code_paragraph

BLACK = RGBColor(0, 0, 0)


def _add_body(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(FIRST_LINE_INDENT_PT)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.font.size = Pt(BODY_PT)
    run.font.color.rgb = BLACK


def render_ast_to_docx(ast: BookAst) -> bytes:
    doc = Document()
    for block in ast.blocks:
        role = block.role
        if role == "book_title":
            p = doc.add_paragraph(block.text)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.font.size = Pt(22)
                r.bold = True
                r.font.color.rgb = BLACK
        elif role == "preface_title":
            p = doc.add_paragraph(block.text)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.font.size = Pt(18)
                r.bold = True
                r.font.color.rgb = BLACK
        elif role == "chapter_title":
            p = doc.add_paragraph(block.text)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.font.size = Pt(CHAPTER_TITLE_PT)
                r.bold = True
                r.font.color.rgb = BLACK
        elif role in ("section_title", "subsection_title"):
            node = block.attrs.get("tiptap_node")
            if isinstance(node, dict):
                docx_block(doc, node)
            else:
                p = doc.add_paragraph(block.text)
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    r.font.size = Pt(SECTION_TITLE_PT if role == "section_title" else 13)
                    r.bold = True
                    r.font.color.rgb = BLACK
        elif role == "body":
            node = block.attrs.get("tiptap_node")
            if isinstance(node, dict):
                docx_block(doc, node)
            else:
                _add_body(doc, block.text)
        elif role == "figure":
            node = block.attrs.get("tiptap_node")
            if isinstance(node, dict):
                if not docx_figure_image_only(doc, node):
                    p = doc.add_paragraph("【图片待生成】")
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p = doc.add_paragraph(block.text)
                for r in p.runs:
                    r.bold = True
                    r.font.size = Pt(CAPTION_PT)
                    r.font.color.rgb = BLACK
        elif role == "figure_caption":
            p = doc.add_paragraph(block.text)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.font.size = Pt(CAPTION_PT)
                r.font.color.rgb = BLACK
        elif role == "table_caption":
            p = doc.add_paragraph(block.text)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(CAPTION_PT)
                r.font.color.rgb = BLACK
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
                    r.font.color.rgb = BLACK
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
