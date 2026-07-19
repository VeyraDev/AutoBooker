"""Structured book export AST: cover → toc → preface → chapters → bibliography."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.publication.book_ast import AstBlock

SectionType = Literal["cover", "toc", "preface", "chapter", "bibliography"]


@dataclass
class TocEntry:
    title: str
    section_type: SectionType
    chapter_index: int | None = None
    """1 = 章/前言等一级；2 = 章内小节（对标出版目录一二级标题）。"""
    level: int = 1
    """目录页码（预估或域更新后由 Word 刷新）。"""
    page: int | None = None


@dataclass
class CoverSection:
    type: Literal["cover"] = "cover"
    title: str = ""
    """封面/版权页元数据：副标题、作者、出版社、ISBN 等。"""
    publication: dict[str, Any] = field(default_factory=dict)
    page_break_after: bool = True


@dataclass
class TocSection:
    type: Literal["toc"] = "toc"
    entries: list[TocEntry] = field(default_factory=list)
    page_break_before: bool = True
    page_break_after: bool = True


@dataclass
class PrefaceSection:
    type: Literal["preface"] = "preface"
    title: str = "前言"
    blocks: list[AstBlock] = field(default_factory=list)
    page_break_before: bool = True
    page_break_after: bool = True


@dataclass
class ChapterSection:
    type: Literal["chapter"] = "chapter"
    chapter_index: int = 0
    title: str = ""
    summary: str = ""
    blocks: list[AstBlock] = field(default_factory=list)
    page_break_before: bool = True


@dataclass
class BibliographySection:
    type: Literal["bibliography"] = "bibliography"
    title: str = "参考文献"
    blocks: list[AstBlock] = field(default_factory=list)
    page_break_before: bool = True


BookExportSection = CoverSection | TocSection | PrefaceSection | ChapterSection | BibliographySection


@dataclass
class BookExportAst:
    title: str
    toc_entries: list[TocEntry] = field(default_factory=list)
    sections: list[BookExportSection] = field(default_factory=list)

    def flatten_blocks(self) -> list[AstBlock]:
        """Linearize for legacy BookAst consumers."""
        blocks: list[AstBlock] = []
        for section in self.sections:
            if section.type == "cover":
                blocks.append(AstBlock(role="book_title", text=section.title))
            elif section.type == "preface":
                blocks.append(AstBlock(role="preface_title", text=section.title))
                blocks.extend(section.blocks)
            elif section.type == "chapter":
                blocks.append(
                    AstBlock(
                        role="chapter_flyleaf",
                        text=section.title,
                        attrs={
                            "chapter_index": section.chapter_index,
                            "summary": getattr(section, "summary", "") or "",
                        },
                    )
                )
                blocks.extend(section.blocks)
            elif section.type == "bibliography":
                blocks.append(
                    AstBlock(
                        role="chapter_title",
                        text=section.title,
                        attrs={"book_end_matter": True},
                    )
                )
                blocks.extend(section.blocks)
        return blocks
