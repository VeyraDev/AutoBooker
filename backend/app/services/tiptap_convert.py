"""将 TipTap / ProseMirror JSON 转为 Markdown 或写入 python-docx 文档。"""

from __future__ import annotations

from typing import Any

from docx import Document
from docx.shared import Pt


def _inline_to_markdown(nodes: list[dict[str, Any]] | None) -> str:
    if not nodes:
        return ""
    parts: list[str] = []
    for node in nodes:
        t = node.get("type")
        if t == "text":
            text = str(node.get("text") or "")
            marks = node.get("marks") or []
            bold = any(m.get("type") == "bold" for m in marks)
            italic = any(m.get("type") == "italic" for m in marks)
            code = any(m.get("type") == "code" for m in marks)
            if code:
                text = f"`{text}`"
            if bold:
                text = f"**{text}**"
            if italic:
                text = f"*{text}*"
            parts.append(text)
        elif t == "hardBreak":
            parts.append("\n")
    return "".join(parts)


def _bullet_indent(depth: int) -> str:
    return "  " * max(0, depth)


def _list_item_body(item: dict[str, Any], depth: int) -> str:
    inner = item.get("content") or []
    parts: list[str] = []
    for child in inner:
        if not isinstance(child, dict):
            continue
        ct = child.get("type")
        if ct in ("bulletList", "orderedList"):
            parts.append(_block_to_markdown(child, depth + 1))
        else:
            parts.append(_block_to_markdown(child, depth))
    return "\n\n".join(p for p in parts if p)


def _block_to_markdown(node: dict[str, Any], depth: int = 0) -> str:
    t = node.get("type")
    if t == "paragraph":
        return _inline_to_markdown(node.get("content"))
    if t == "heading":
        level = int((node.get("attrs") or {}).get("level") or 1)
        level = max(1, min(6, level))
        return f"{'#' * level} {_inline_to_markdown(node.get('content'))}"
    if t == "blockquote":
        inner = _blocks_to_markdown(node.get("content") or [], depth)
        if not inner:
            return "> "
        return "\n".join(f"> {line}" for line in inner.split("\n"))
    if t == "codeBlock":
        raw = _inline_to_markdown(node.get("content"))
        lang = str((node.get("attrs") or {}).get("language") or "").strip()
        head = f"```{lang}\n" if lang else "```\n"
        return f"{head}{raw}\n```"
    if t == "horizontalRule":
        return "---"
    if t == "bulletList":
        lines: list[str] = []
        for item in node.get("content") or []:
            if not isinstance(item, dict) or item.get("type") != "listItem":
                continue
            body = _list_item_body(item, depth)
            pad = _bullet_indent(depth)
            first = True
            for line in body.split("\n"):
                if first:
                    lines.append(f"{pad}- {line}")
                    first = False
                else:
                    lines.append(f"{pad}  {line}")
        return "\n".join(lines)
    if t == "orderedList":
        start = (node.get("attrs") or {}).get("start")
        idx = int(start) if isinstance(start, int) and start >= 1 else 1
        lines_o: list[str] = []
        for item in node.get("content") or []:
            if not isinstance(item, dict) or item.get("type") != "listItem":
                continue
            body = _list_item_body(item, depth)
            pad = _bullet_indent(depth)
            first = True
            for line in body.split("\n"):
                if first:
                    lines_o.append(f"{pad}{idx}. {line}")
                    first = False
                else:
                    lines_o.append(f"{pad}   {line}")
            idx += 1
        return "\n".join(lines_o)
    if t == "listItem":
        return _list_item_body(node, depth)
    return ""


def _blocks_to_markdown(nodes: list[dict[str, Any]], depth: int = 0) -> str:
    chunks: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        s = _block_to_markdown(node, depth)
        if s:
            chunks.append(s)
    return "\n\n".join(chunks)


def tiptap_json_to_markdown(doc: dict[str, Any] | None) -> str:
    if not doc or doc.get("type") != "doc":
        return ""
    return _blocks_to_markdown(doc.get("content") or [])


def chapter_content_to_markdown(content: dict[str, Any] | None) -> str:
    if not content or not isinstance(content, dict):
        return ""
    tj = content.get("tiptap_json")
    if isinstance(tj, dict):
        return tiptap_json_to_markdown(tj).strip()
    tx = content.get("text")
    if isinstance(tx, str) and tx.strip():
        return tx.strip()
    return ""


# --- DOCX ---


def _add_inline_to_paragraph(paragraph, nodes: list[dict[str, Any]] | None) -> None:
    if not nodes:
        return
    for node in nodes:
        t = node.get("type")
        if t == "text":
            run = paragraph.add_run(str(node.get("text") or ""))
            for m in node.get("marks") or []:
                mt = m.get("type")
                if mt == "bold":
                    run.bold = True
                elif mt == "italic":
                    run.italic = True
                elif mt == "code":
                    run.font.name = "Consolas"
                    run.font.size = Pt(10)
        elif t == "hardBreak":
            paragraph.add_run("\n")


def _add_paragraph_bullet(doc: Document, content: list[dict[str, Any]] | None) -> None:
    try:
        p = doc.add_paragraph(style="List Bullet")
    except Exception:
        p = doc.add_paragraph()
        p.add_run("• ")
    _add_inline_to_paragraph(p, content)


def _add_paragraph_numbered(doc: Document, content: list[dict[str, Any]] | None) -> None:
    try:
        p = doc.add_paragraph(style="List Number")
    except Exception:
        p = doc.add_paragraph()
    _add_inline_to_paragraph(p, content)


def _docx_block(doc: Document, node: dict[str, Any]) -> None:
    t = node.get("type")
    if t == "paragraph":
        p = doc.add_paragraph()
        _add_inline_to_paragraph(p, node.get("content"))
        return
    if t == "heading":
        level = int((node.get("attrs") or {}).get("level") or 1)
        level = max(1, min(3, level))
        doc.add_heading(_inline_to_markdown(node.get("content")), level=level)
        return
    if t == "bulletList":
        for item in node.get("content") or []:
            if not isinstance(item, dict) or item.get("type") != "listItem":
                continue
            for sub in item.get("content") or []:
                if isinstance(sub, dict) and sub.get("type") == "paragraph":
                    _add_paragraph_bullet(doc, sub.get("content"))
                elif isinstance(sub, dict):
                    _docx_block(doc, sub)
        return
    if t == "orderedList":
        for item in node.get("content") or []:
            if not isinstance(item, dict) or item.get("type") != "listItem":
                continue
            for sub in item.get("content") or []:
                if isinstance(sub, dict) and sub.get("type") == "paragraph":
                    _add_paragraph_numbered(doc, sub.get("content"))
                elif isinstance(sub, dict):
                    _docx_block(doc, sub)
        return
    if t == "blockquote":
        for sub in node.get("content") or []:
            if isinstance(sub, dict) and sub.get("type") == "paragraph":
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18)
                _add_inline_to_paragraph(p, sub.get("content"))
        return
    if t == "codeBlock":
        p = doc.add_paragraph()
        run = p.add_run(_inline_to_markdown(node.get("content")))
        run.font.name = "Consolas"
        run.font.size = Pt(10)
        return
    if t == "horizontalRule":
        doc.add_paragraph("—" * 24)


def append_tiptap_to_document(doc: Document, tiptap: dict[str, Any] | None) -> None:
    if not tiptap or tiptap.get("type") != "doc":
        return
    for node in tiptap.get("content") or []:
        if isinstance(node, dict):
            _docx_block(doc, node)


def append_chapter_content_to_document(doc: Document, content: dict[str, Any] | None) -> None:
    if not content or not isinstance(content, dict):
        return
    tj = content.get("tiptap_json")
    if isinstance(tj, dict):
        append_tiptap_to_document(doc, tj)
        return
    tx = content.get("text")
    if isinstance(tx, str) and tx.strip():
        for para in tx.strip().split("\n\n"):
            doc.add_paragraph(para.replace("\n", " "))
