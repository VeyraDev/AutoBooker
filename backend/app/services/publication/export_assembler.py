"""Assemble BookExportAst from Book + chapters."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.models.figure import Figure
from app.services.preface_service import get_preface
from app.services.publication.book_ast import AstBlock
from app.services.publication.book_ast_builder import export_chapter_title
from app.services.publication.export_ast import (
    BibliographySection,
    BookExportAst,
    ChapterSection,
    CoverSection,
    PrefaceSection,
    TocEntry,
    TocSection,
)
from app.services.figure_service import repair_figure_file
from app.services.figures.export_assets import prepare_book_figures_for_export
from app.services.tiptap_convert import _inline_to_markdown

TABLE_CAPTION_RE = re.compile(r"^表\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]\s*(.+)$")
FIGURE_CAPTION_RE = re.compile(r"^图\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]\s*(.+)$")


def _strip_url_query(url: str | None) -> str:
    return str(url or "").strip().split("?", 1)[0].split("#", 1)[0].strip()


def _heading_role(level: int) -> str:
    if level <= 2:
        return "section_title"
    return "subsection_title"


def _looks_like_flat_table_line(text: str) -> bool:
    return "\t" in text and text.count("\t") >= 1


def _walk_tiptap(
    nodes: list[dict[str, Any]],
    blocks: list[AstBlock],
    *,
    book_id: str,
    chapter_index: int,
    table_counter: list[int],
    figure_by_id: dict[str, Figure],
    db: Session | None = None,
) -> None:
    from app.services.publication import book_ast_builder as legacy

    legacy._walk_tiptap(
        nodes,
        blocks,
        book_id=book_id,
        chapter_index=chapter_index,
        table_counter=table_counter,
        figure_by_id=figure_by_id,
        db=db,
    )


def _blocks_from_tiptap(
    tiptap_json: dict[str, Any] | None,
    *,
    book_id: str,
    chapter_index: int,
    figure_by_id: dict[str, Figure],
    db: Session | None = None,
) -> list[AstBlock]:
    blocks: list[AstBlock] = []
    if not isinstance(tiptap_json, dict):
        return blocks
    _walk_tiptap(
        tiptap_json.get("content") or [],
        blocks,
        book_id=book_id,
        chapter_index=chapter_index,
        table_counter=[0],
        figure_by_id=figure_by_id,
        db=db,
    )
    return blocks


def _chapter_summary_line(ch: Chapter, blocks: list[AstBlock]) -> str:
    raw = (getattr(ch, "summary", None) or "").strip()
    if raw:
        return raw.replace("\n", " ").strip()[:80]
    for block in blocks:
        if block.role == "body" and (block.text or "").strip():
            return (block.text or "").replace("\n", " ").strip()[:80]
    return ""


def _estimate_pages_from_blocks(blocks: list[AstBlock], *, base: int = 1) -> int:
    """Rough page estimate (~400 Chinese chars / page) for TOC page numbers."""
    chars = 0
    for block in blocks:
        chars += len(block.text or "")
        node = block.attrs.get("tiptap_node")
        if isinstance(node, dict):
            chars += len(_inline_to_markdown(node.get("content")) or "")
    return max(base, (chars + 399) // 400)


def _section_titles_for_toc(blocks: list[AstBlock]) -> list[str]:
    """Collect chapter-internal section titles（二级目录）。"""
    titles: list[str] = []
    for block in blocks:
        if block.role != "section_title":
            continue
        title = (block.text or "").strip()
        if title:
            titles.append(title)
    return titles


def build_book_export_ast(
    book: Book,
    chapters: list[Chapter],
    db: Session,
    *,
    publication_info: dict | None = None,
) -> BookExportAst:
    from app.services.publication.publication_info import normalize_publication_info

    pub = normalize_publication_info(
        publication_info if publication_info is not None else getattr(book, "publication_info", None),
        fallback_title=book.title or "未命名",
    )
    title = pub.get("title") or book.title or "未命名"
    ast = BookExportAst(title=title)

    book_pk = getattr(book, "id", None)
    figures = db.query(Figure).filter(Figure.book_id == book_pk).all() if book_pk else []
    for fig in figures:
        repair_figure_file(fig, db)
    prepare_book_figures_for_export(figures, db)
    figure_by_id = {str(f.id): f for f in figures}
    book_id = str(book_pk or "")

    from app.services.citation_service import is_bibliography_chapter

    toc_entries: list[TocEntry] = []
    sections: list = []

    pf = get_preface(book)
    has_preface = bool(pf.get("enabled") and isinstance(pf.get("tiptap_json"), dict))

    sections.append(CoverSection(title=title, publication=pub))

    preface_blocks: list[AstBlock] = []
    if has_preface:
        preface_blocks = _blocks_from_tiptap(
            pf["tiptap_json"],
            book_id=book_id,
            chapter_index=0,
            figure_by_id={},
            db=db,
        )

    content_chapters = [ch for ch in chapters if not is_bibliography_chapter(ch)]
    chapter_payloads: list[tuple[Chapter, str, list[AstBlock]]] = []
    for ch in content_chapters:
        ch_title = export_chapter_title(ch)
        meta = ch.content if isinstance(ch.content, dict) else {}
        chapter_blocks: list[AstBlock] = []
        tj = meta.get("tiptap_json")
        if isinstance(tj, dict):
            chapter_blocks = _blocks_from_tiptap(
                tj,
                book_id=book_id,
                chapter_index=ch.index,
                figure_by_id=figure_by_id,
                db=db,
            )
        elif meta.get("text"):
            chapter_blocks.append(AstBlock(role="body", text=str(meta.get("text"))[:50000]))
        chapter_payloads.append((ch, ch_title, chapter_blocks))

    raw_bibliography = getattr(book, "bibliography", None)
    bibliography = raw_bibliography if isinstance(raw_bibliography, dict) else {}
    bibliography_text = str(bibliography.get("text") or "").strip()
    bib_blocks: list[AstBlock] = []
    bib_title = str(bibliography.get("title") or "参考文献")
    if bibliography_text:
        bib_blocks = _blocks_from_tiptap(
            bibliography.get("tiptap_json") if isinstance(bibliography.get("tiptap_json"), dict) else None,
            book_id=book_id,
            chapter_index=0,
            figure_by_id={},
            db=db,
        )
        if not bib_blocks:
            for line in bibliography_text.split("\n\n"):
                if line.strip():
                    bib_blocks.append(AstBlock(role="body", text=line.strip()))

    # 先收集目录条目，再按正式书籍顺序（封面/版权 → 目录 → 前言 → 正文）估算页码
    if has_preface:
        toc_entries.append(TocEntry(title="前言", section_type="preface", level=1))
    for ch, ch_title, chapter_blocks in chapter_payloads:
        toc_entries.append(
            TocEntry(
                title=ch_title,
                section_type="chapter",
                chapter_index=ch.index,
                level=1,
            )
        )
        for sec_title in _section_titles_for_toc(chapter_blocks):
            toc_entries.append(
                TocEntry(
                    title=sec_title,
                    section_type="chapter",
                    chapter_index=ch.index,
                    level=2,
                )
            )
    if bib_blocks:
        toc_entries.append(TocEntry(title=bib_title, section_type="bibliography", level=1))

    # 页码规范：阿拉伯数字从正文第一章第 1 页起；前言等前置不计阿拉伯页码
    page_cursor = 1
    entry_i = 0
    if has_preface:
        toc_entries[entry_i].page = None  # 前言列入目录，但不占正文页码
        entry_i += 1
    for _ch, _title, chapter_blocks in chapter_payloads:
        # 章过渡 1 页；每节另起一页计入目录估页
        toc_entries[entry_i].page = page_cursor
        entry_i += 1
        page_cursor += 1  # chapter flyleaf
        sec_count = len(_section_titles_for_toc(chapter_blocks))
        for _ in range(sec_count):
            toc_entries[entry_i].page = page_cursor
            entry_i += 1
            page_cursor += 1  # 每节另起一页
        # 正文估页（扣除已为各节各计的 1 页中一部分重叠，仍用整章字数作下限）
        body_pages = _estimate_pages_from_blocks(chapter_blocks)
        page_cursor += max(0, body_pages - sec_count)
    if bib_blocks:
        toc_entries[entry_i].page = page_cursor

    sections.append(TocSection(entries=list(toc_entries)))
    ast.toc_entries = list(toc_entries)

    if has_preface:
        sections.append(PrefaceSection(blocks=preface_blocks))

    for ch, ch_title, chapter_blocks in chapter_payloads:
        sections.append(
            ChapterSection(
                chapter_index=ch.index,
                title=ch_title,
                summary=_chapter_summary_line(ch, chapter_blocks),
                blocks=chapter_blocks,
            )
        )

    if bib_blocks:
        sections.append(BibliographySection(title=bib_title, blocks=bib_blocks))

    ast.sections = sections
    return ast
