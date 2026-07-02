"""Export page numbers for DOCX and PDF."""

from __future__ import annotations

import io

import fitz
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.services.publication.publication_styles import PDF_PAGE_MARGIN_PT


def _append_page_field(run) -> None:
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(fld_end)


def add_docx_page_numbers(doc: Document) -> None:
    """在每节页脚居中插入 Word PAGE 域。"""
    for section in doc.sections:
        footer = section.footer
        footer.is_linked_to_previous = False
        paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p_element = paragraph._p
        for child in list(p_element):
            if child.tag.endswith("r"):
                p_element.remove(child)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run()
        _append_page_field(run)


def add_pdf_page_numbers(pdf_bytes: bytes) -> bytes:
    """在每页底部居中绘制阿拉伯数字页码。"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for index, page in enumerate(doc):
            rect = page.rect
            box = fitz.Rect(
                PDF_PAGE_MARGIN_PT,
                rect.height - PDF_PAGE_MARGIN_PT + 8,
                rect.width - PDF_PAGE_MARGIN_PT,
                rect.height - 16,
            )
            page.insert_textbox(
                box,
                str(index + 1),
                fontsize=10,
                fontname="china-s",
                color=(0, 0, 0),
                align=fitz.TEXT_ALIGN_CENTER,
            )
        return doc.tobytes()
    finally:
        doc.close()
