"""Render BookExportAst to Markdown with unified page breaks."""

from __future__ import annotations

from app.services.publication.export_ast import BookExportAst
from app.services.publication.book_ast import AstBlock
from app.services.tiptap_convert import _inline_to_markdown

PAGE_BREAK = "<!-- pagebreak -->"


def _append_page_break(lines: list[str]) -> None:
    if not lines:
        return
    for line in reversed(lines):
        if not line.strip():
            continue
        if line == PAGE_BREAK:
            return
        break
    lines.append(PAGE_BREAK)
    lines.append("")


def _block_to_markdown(block: AstBlock) -> str:
    role = block.role
    if role == "body":
        node = block.attrs.get("tiptap_node")
        if isinstance(node, dict):
            return _inline_to_markdown(node.get("content"))
        return block.text
    if role in ("section_title", "subsection_title"):
        level = max(2, min(6, block.level or 3))
        prefix = "#" * level
        return f"{prefix} {block.text}"
    if role == "figure_caption":
        return f"*{block.text}*"
    if role == "table_caption":
        return f"**{block.text}**"
    if role == "figure":
        return f"![{block.text}](figure)"
    if role == "code":
        return f"```\n{block.text}\n```"
    if role == "blockquote":
        return f"> {block.text}" if block.text else "> "
    return block.text


def _section_blocks_to_md(blocks: list[AstBlock]) -> list[str]:
    lines: list[str] = []
    for block in blocks:
        text = _block_to_markdown(block)
        if text.strip():
            lines.append(text)
            lines.append("")
    return lines


def render_export_ast_to_markdown(ast: BookExportAst) -> str:
    lines: list[str] = []

    for section in ast.sections:
        if section.type == "cover":
            if section.page_break_after:
                if lines:
                    _append_page_break(lines)
            pub = section.publication if isinstance(getattr(section, "publication", None), dict) else {}
            title = (pub.get("title") or section.title or ast.title).strip()
            lines.append(f"# {title}")
            lines.append("")
            if pub.get("subtitle"):
                lines.append(f"**{pub['subtitle']}**")
                lines.append("")
            if pub.get("author"):
                lines.append(f"著者：{pub['author']}")
            if pub.get("publisher"):
                lines.append(f"出版社：{pub['publisher']}")
            if pub.get("publish_year"):
                lines.append(f"出版年：{pub['publish_year']}")
            if pub.get("isbn"):
                lines.append(f"ISBN：{pub['isbn']}")
            if any(pub.get(k) for k in ("author", "publisher", "publish_year", "isbn", "subtitle")):
                lines.append("")
            if section.page_break_after:
                _append_page_break(lines)
        elif section.type == "toc":
            if section.page_break_before and lines:
                _append_page_break(lines)
            lines.append("## 目录")
            lines.append("")
            for entry in section.entries:
                indent = "  " if getattr(entry, "level", 1) > 1 else ""
                page = f" …… {entry.page}" if entry.page is not None else ""
                lines.append(f"{indent}- {entry.title}{page}")
            lines.append("")
            if section.page_break_after:
                _append_page_break(lines)
        elif section.type == "preface":
            if section.page_break_before:
                _append_page_break(lines)
            lines.append(f"## {section.title}")
            lines.append("")
            lines.extend(_section_blocks_to_md(section.blocks))
            if section.page_break_after:
                _append_page_break(lines)
        elif section.type == "chapter":
            if section.page_break_before:
                _append_page_break(lines)
            lines.append(f"## {section.title}")
            lines.append("")
            lines.extend(_section_blocks_to_md(section.blocks))
        elif section.type == "bibliography":
            if section.page_break_before:
                _append_page_break(lines)
            lines.append(f"## {section.title}")
            lines.append("")
            lines.extend(_section_blocks_to_md(section.blocks))

    return "\n".join(lines).rstrip() + "\n"
