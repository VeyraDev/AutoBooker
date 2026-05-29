"""Book document AST for unified export."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlockRole = Literal[
    "book_title",
    "preface_title",
    "chapter_title",
    "section_title",
    "subsection_title",
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
