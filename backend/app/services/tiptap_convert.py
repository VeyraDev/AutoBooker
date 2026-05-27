"""将 TipTap / ProseMirror JSON 转为 Markdown 或写入 python-docx 文档。"""

from __future__ import annotations

from typing import Any

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.shared import Inches, Pt, RGBColor

BLACK = RGBColor(0, 0, 0)
HEADING_PT = {1: 22, 2: 18, 3: 16, 4: 14, 5: 13, 6: 12}
BODY_PT = 12
CODE_PT = 10


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
    if t in ("diagramBlock", "mermaidBlock"):
        attrs = node.get("attrs") or {}
        engine = str(attrs.get("engine") or "graphviz")
        code = str(attrs.get("code") or "").strip()
        lang = "plantuml" if engine == "plantuml" else "dot"
        return f"```{lang}\n{code}\n```"
    if t == "figureBlock":
        attrs = node.get("attrs") or {}
        num = str(attrs.get("figureNumber") or "")
        caption = str(attrs.get("caption") or attrs.get("rawAnnotation") or "")
        url = str(attrs.get("fileUrl") or "")
        label = f"图 {num}" if num else "图"
        if url:
            return f"![{label}]({url})\n\n*{label} 图解：{caption}*"
        raw = str(attrs.get("rawAnnotation") or caption)
        ftype = str(attrs.get("figureType") or "figure").upper()
        tag = "FLOWCHART" if ftype == "FLOWCHART" else "CHART" if ftype == "CHART" else "SCREENSHOT" if ftype == "SCREENSHOT" else "FIGURE"
        return f"[{tag}: {raw}]"
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


def _style_run(run, *, size_pt: int = BODY_PT, bold: bool = False, italic: bool = False, mono: bool = False) -> None:
    run.font.color.rgb = BLACK
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    if mono:
        run.font.name = "Consolas"


def _add_inline_to_paragraph(paragraph, nodes: list[dict[str, Any]] | None, *, size_pt: int = BODY_PT) -> None:
    if not nodes:
        return
    for node in nodes:
        t = node.get("type")
        if t == "text":
            run = paragraph.add_run(str(node.get("text") or ""))
            bold = italic = mono = False
            for m in node.get("marks") or []:
                mt = m.get("type")
                if mt == "bold":
                    bold = True
                elif mt == "italic":
                    italic = True
                elif mt == "code":
                    mono = True
            _style_run(run, size_pt=CODE_PT if mono else size_pt, bold=bold, italic=italic, mono=mono)
        elif t == "hardBreak":
            run = paragraph.add_run("\n")
            _style_run(run, size_pt=size_pt)


def _body_paragraph_format(p) -> None:
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = 1.5
    pf.space_after = Pt(6)


def _add_paragraph_bullet(doc: Document, content: list[dict[str, Any]] | None) -> None:
    try:
        p = doc.add_paragraph(style="List Bullet")
    except Exception:
        p = doc.add_paragraph()
        r = p.add_run("• ")
        _style_run(r)
    _body_paragraph_format(p)
    _add_inline_to_paragraph(p, content)


def _add_paragraph_numbered(doc: Document, content: list[dict[str, Any]] | None) -> None:
    try:
        p = doc.add_paragraph(style="List Number")
    except Exception:
        p = doc.add_paragraph()
    _body_paragraph_format(p)
    _add_inline_to_paragraph(p, content)


def _table_cell_text(cell: dict[str, Any]) -> str:
    parts: list[str] = []
    for sub in cell.get("content") or []:
        if isinstance(sub, dict) and sub.get("type") == "paragraph":
            parts.append(_inline_to_markdown(sub.get("content")))
    return " ".join(p for p in parts if p).strip()


def _docx_block(doc: Document, node: dict[str, Any]) -> None:
    t = node.get("type")
    if t == "paragraph":
        p = doc.add_paragraph()
        _body_paragraph_format(p)
        _add_inline_to_paragraph(p, node.get("content"))
        return
    if t == "heading":
        level = int((node.get("attrs") or {}).get("level") or 1)
        level = max(1, min(6, level))
        h = doc.add_heading(_inline_to_markdown(node.get("content")), level=min(level, 3))
        for para in h.paragraphs:
            for run in para.runs:
                _style_run(run, size_pt=HEADING_PT.get(level, 14), bold=True)
        return
    if t == "table":
        rows_in = [r for r in (node.get("content") or []) if isinstance(r, dict) and r.get("type") == "tableRow"]
        if not rows_in:
            return
        max_cols = 0
        for row in rows_in:
            cells = [c for c in (row.get("content") or []) if isinstance(c, dict)]
            max_cols = max(max_cols, len(cells))
        max_cols = max(1, max_cols)
        table = doc.add_table(rows=len(rows_in), cols=max_cols)
        try:
            table.style = "Table Grid"
        except Exception:
            pass
        for ri, row in enumerate(rows_in):
            cells = [c for c in (row.get("content") or []) if isinstance(c, dict)]
            for ci in range(max_cols):
                cell = cells[ci] if ci < len(cells) else {}
                text = _table_cell_text(cell) if cell else ""
                cell_p = table.rows[ri].cells[ci].paragraphs[0]
                cell_p.clear()
                if text:
                    run = cell_p.add_run(text)
                    _style_run(run, size_pt=BODY_PT)
        doc.add_paragraph("")
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
                _body_paragraph_format(p)
                _add_inline_to_paragraph(p, sub.get("content"))
        return
    if t == "codeBlock":
        p = doc.add_paragraph()
        _body_paragraph_format(p)
        run = p.add_run(_inline_to_markdown(node.get("content")))
        _style_run(run, size_pt=CODE_PT, mono=True)
        return
    if t in ("diagramBlock", "mermaidBlock"):
        attrs = node.get("attrs") or {}
        code = str(attrs.get("code") or "").strip()
        lang = str(attrs.get("engine") or "mermaid")
        p = doc.add_paragraph()
        _body_paragraph_format(p)
        run = p.add_run(f"[{lang}]\n{code}")
        _style_run(run, size_pt=CODE_PT, mono=True)
        return
    if t == "horizontalRule":
        p = doc.add_paragraph("—" * 24)
        for run in p.runs:
            _style_run(run)
        return
    if t == "figureBlock":
        attrs = node.get("attrs") or {}
        path = str(attrs.get("fileUrl") or attrs.get("file_path") or "")
        caption = str(attrs.get("caption") or attrs.get("rawAnnotation") or "")
        num = str(attrs.get("figureNumber") or "")
        label = f"图 {num}" if num else "图"
        if path.startswith("/static/figures/"):
            from app.config import settings

            local = settings.figures_path / path.replace("/static/figures/", "", 1)
            if local.is_file():
                lp = doc.add_paragraph(label)
                for run in lp.runs:
                    _style_run(run, bold=True)
                doc.add_picture(str(local), width=Inches(5.5))
                if caption:
                    cp = doc.add_paragraph(f"图解：{caption}")
                    cp.paragraph_format.space_before = Pt(6)
                    for run in cp.runs:
                        _style_run(run, italic=True)
                return
        p = doc.add_paragraph(f"[{label}: {caption or '待生成'}]")
        for run in p.runs:
            _style_run(run)
        return


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
