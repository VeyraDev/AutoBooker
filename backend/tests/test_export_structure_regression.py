"""Export structure regression: cover → toc → preface → chapters."""

from __future__ import annotations

import io
from types import SimpleNamespace
from uuid import uuid4

from docx import Document

from app.services.publication.book_ast import AstBlock
from app.services.publication.export_assembler import build_book_export_ast
from app.services.publication.export_ast import (
    BookExportAst,
    ChapterSection,
    CoverSection,
    PrefaceSection,
    TocEntry,
    TocSection,
)
from app.services.publication.markdown_renderer import PAGE_BREAK, render_export_ast_to_markdown
from app.services.publication.publication_renderer_docx import render_export_ast_to_docx
from app.services.publication.publication_renderer_pdf import _export_ast_to_linear_book_ast


class _FakeDb:
    class _Query:
        def __init__(self, figures):
            self._figures = figures

        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return self._figures

    def __init__(self, figures=None):
        self._figures = figures or []

    def query(self, *_args, **_kwargs):
        return self._Query(self._figures)


def _chapter(index: int, title: str, text: str = "正文段落。"):
    return SimpleNamespace(
        index=index,
        title=title,
        summary=None,
        content={
            "tiptap_json": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": text}],
                    }
                ],
            }
        },
    )


def test_export_ast_structure_with_preface_and_chapters(monkeypatch):
    book_id = uuid4()
    book = SimpleNamespace(
        id=book_id,
        title="测试书稿",
        bibliography={"title": "参考文献", "text": "[1] Author. Title."},
    )
    chapters = [_chapter(1, "第一章 引言"), _chapter(2, "第二章 方法")]

    monkeypatch.setattr(
        "app.services.publication.export_assembler.get_preface",
        lambda _book: {
            "enabled": True,
            "tiptap_json": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "前言内容。"}],
                    }
                ],
            },
        },
    )
    monkeypatch.setattr(
        "app.services.publication.export_assembler.prepare_book_figures_for_export",
        lambda _figs, _db=None: None,
    )
    monkeypatch.setattr(
        "app.services.publication.export_assembler.repair_figure_file",
        lambda _fig, _db: None,
    )
    monkeypatch.setattr(
        "app.services.citation_service.is_bibliography_chapter",
        lambda _ch: False,
    )

    ast: BookExportAst = build_book_export_ast(book, chapters, _FakeDb())
    section_types = [s.type for s in ast.sections]
    assert section_types[0] == "cover"
    assert section_types[1] == "toc"
    assert "preface" in section_types
    assert section_types.count("chapter") == 2
    assert section_types[-1] == "bibliography"

    toc_titles = [e.title for e in ast.toc_entries]
    assert "前言" in toc_titles
    assert "第一章 引言" in toc_titles
    assert "第二章 方法" in toc_titles

    md = render_export_ast_to_markdown(ast)
    assert md.index("# 测试书稿") < md.index("## 目录")
    assert md.index("## 目录") < md.index("## 前言")
    assert md.index("## 前言") < md.index("## 第一章 引言")
    assert "<!-- pagebreak -->" in md


def test_export_ast_without_preface(monkeypatch):
    book = SimpleNamespace(id=uuid4(), title="无前言书", bibliography=None)
    chapters = [_chapter(1, "第一章")]

    monkeypatch.setattr(
        "app.services.publication.export_assembler.get_preface",
        lambda _book: {"enabled": False},
    )
    monkeypatch.setattr(
        "app.services.publication.export_assembler.prepare_book_figures_for_export",
        lambda _figs, _db=None: None,
    )
    monkeypatch.setattr(
        "app.services.publication.export_assembler.repair_figure_file",
        lambda _fig, _db: None,
    )
    monkeypatch.setattr(
        "app.services.citation_service.is_bibliography_chapter",
        lambda _ch: False,
    )

    ast = build_book_export_ast(book, chapters, _FakeDb())
    assert not any(s.type == "preface" for s in ast.sections)
    assert ast.toc_entries[0].title == "第一章"


def _minimal_export_ast() -> BookExportAst:
    entries = [
        TocEntry(title="前言", section_type="preface"),
        TocEntry(title="第一章", section_type="chapter", chapter_index=1),
    ]
    return BookExportAst(
        title="无空白页测试",
        toc_entries=entries,
        sections=[
            CoverSection(title="无空白页测试"),
            TocSection(entries=entries),
            PrefaceSection(blocks=[AstBlock(role="body", text="前言内容。")]),
            ChapterSection(
                chapter_index=1,
                title="第一章",
                blocks=[AstBlock(role="body", text="正文内容。")],
            ),
        ],
    )


def test_markdown_export_coalesces_section_page_breaks():
    md = render_export_ast_to_markdown(_minimal_export_ast())

    assert "catalog" not in md.lower()
    assert "编目" not in md
    assert f"{PAGE_BREAK}\n\n{PAGE_BREAK}" not in md
    assert md.index("# 无空白页测试") < md.index("## 目录") < md.index("## 前言") < md.index("## 第一章")


def test_pdf_linear_ast_coalesces_section_page_breaks():
    linear = _export_ast_to_linear_book_ast(_minimal_export_ast())
    roles = [
        "page_break" if block.role == "body" and block.attrs.get("force_page_break") else block.role
        for block in linear.blocks
    ]

    assert roles.count("page_break") == 3
    for left, right in zip(roles, roles[1:]):
        assert (left, right) != ("page_break", "page_break")


def _is_page_break_only_paragraph(paragraph) -> bool:
    text_nodes = paragraph._p.xpath(".//w:t")
    if any((node.text or "").strip() for node in text_nodes):
        return False
    return bool(paragraph._p.xpath(".//w:br[@w:type='page']"))


def test_docx_export_coalesces_section_page_breaks():
    docx_bytes = render_export_ast_to_docx(_minimal_export_ast())
    doc = Document(io.BytesIO(docx_bytes))
    flags = [_is_page_break_only_paragraph(paragraph) for paragraph in doc.paragraphs]

    assert sum(flags) == 3
    for left, right in zip(flags, flags[1:]):
        assert not (left and right)
