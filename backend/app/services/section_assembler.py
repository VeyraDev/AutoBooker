"""Legacy re-exports — chapter assembly now uses Markdown split in chapter_markdown_assembler."""

from app.services.chapter_markdown_assembler import (
    assemble_chapter_tiptap_from_markdown,
    compute_section_word_budgets,
    process_chapter_generation_result,
)

__all__ = [
    "assemble_chapter_tiptap_from_markdown",
    "compute_section_word_budgets",
    "process_chapter_generation_result",
]
