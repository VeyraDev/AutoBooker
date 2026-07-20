"""Book document AST for unified export."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlockRole = Literal[
    "book_title",
    "preface_title",
    "chapter_title",
    "chapter_flyleaf",
    "section_title",
    "section_flyleaf",
    "subsection_title",
    "toc_entry",
    "body",
    "figure",
    "figure_caption",
    "table",
    "table_caption",
    "code",
    "blockquote",
    "list",
]


@dataclass
class AstBlock:
    role: BlockRole
    text: str = ""
    level: int = 0
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class BookAst:
    title: str
    blocks: list[AstBlock] = field(default_factory=list)
