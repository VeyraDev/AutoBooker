"""Convert chapter section Markdown bodies to TipTap JSON (backend mirror of frontend parser)."""

from __future__ import annotations

import re
from typing import Any

TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")
CAPTION_LINE_RE = re.compile(r"^(表|图)\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]")


def _parse_inline_bold(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    out: list[dict[str, Any]] = []
    for m in re.finditer(r"\*\*([^*]+)\*\*", text):
        if m.start() > 0:
            out.append({"type": "text", "text": text[: m.start()]})
        out.append({"type": "text", "text": m.group(1), "marks": [{"type": "bold"}]})
        text = text[m.end() :]
    if text:
        out.append({"type": "text", "text": text})
    if not out:
        out.append({"type": "text", "text": text or ""})
    return out


def _split_table_cells(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def _table_separator(col_count: int) -> str:
    cols = ["---"] * max(1, col_count)
    return "| " + " | ".join(cols) + " |"


_PID_COMMENT_RE = re.compile(r"<!--\s*pid:[^>]+-->\s*", re.I)
_EMPTY_PID_LIST_PAIR_RE = re.compile(
    r"- <!--\s*pid:[^>]+-->\s*\n- \s*\n",
    re.I,
)
_SPURIOUS_DASH_LIST_LINE_RE = re.compile(r"^- -\s*$", re.M)


def repair_empty_pid_list_pairs(markdown: str) -> str:
    return _EMPTY_PID_LIST_PAIR_RE.sub("", markdown or "")


def drop_spurious_dash_list_lines(markdown: str) -> str:
    text = markdown or ""
    if len(_SPURIOUS_DASH_LIST_LINE_RE.findall(text)) < 5:
        return text
    lines = [
        line
        for line in text.replace("\r\n", "\n").split("\n")
        if not re.match(r"^- -\s*$", line.strip()) and line.strip() != "-"
    ]
    return "\n".join(lines)


def strip_review_pid_comments(markdown: str) -> str:
    return _PID_COMMENT_RE.sub("", markdown or "")


def prepare_source_markdown(markdown: str) -> str:
    from app.services.repair_inline_math import repair_fragmented_inline_math

    repaired = repair_empty_pid_list_pairs(markdown)
    stripped = strip_review_pid_comments(repaired)
    normalized = normalize_gfm_tables(drop_spurious_dash_list_lines(stripped))
    return repair_fragmented_inline_math(normalized)


def normalize_gfm_tables(markdown: str) -> str:
    """补 GFM 表头分隔行，并合并被空行拆开的表格行。"""
    lines = strip_review_pid_comments(markdown).replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if TABLE_ROW_RE.match(line):
            table_lines: list[str] = []
            while i < len(lines):
                cur = lines[i]
                if TABLE_ROW_RE.match(cur) or TABLE_SEP_RE.match(cur):
                    table_lines.append(cur)
                    i += 1
                    continue
                if not cur.strip() and i + 1 < len(lines) and TABLE_ROW_RE.match(lines[i + 1]):
                    i += 1
                    continue
                break
            if table_lines:
                if len(table_lines) == 1:
                    cols = len(_split_table_cells(table_lines[0]))
                    table_lines.append(_table_separator(cols))
                elif not TABLE_SEP_RE.match(table_lines[1]):
                    cols = len(_split_table_cells(table_lines[0]))
                    table_lines.insert(1, _table_separator(cols))
                out.append("\n".join(table_lines))
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _table_cell_node(text: str, *, header: bool) -> dict[str, Any]:
    return {
        "type": "tableHeader" if header else "tableCell",
        "content": [{"type": "paragraph", "content": _parse_inline_bold(text)}],
    }


def _parse_table_rows(lines: list[str], start: int) -> tuple[dict[str, Any] | None, int]:
    raw_rows: list[list[str]] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if TABLE_SEP_RE.match(line):
            i += 1
            continue
        if not TABLE_ROW_RE.match(line):
            break
        raw_rows.append(_split_table_cells(line))
        i += 1
    if not raw_rows:
        return None, start
    max_cols = max(len(r) for r in raw_rows)
    for row in raw_rows:
        while len(row) < max_cols:
            row.append("")
    table_rows: list[dict[str, Any]] = [
        {
            "type": "tableRow",
            "content": [_table_cell_node(cell, header=True) for cell in raw_rows[0]],
        }
    ]
    for row in raw_rows[1:]:
        table_rows.append(
            {
                "type": "tableRow",
                "content": [_table_cell_node(cell, header=False) for cell in row],
            }
        )
    return {"type": "table", "content": table_rows}, i


def _parse_paragraph_inline(text: str) -> list[dict[str, Any]]:
    """段落内联：支持 $...$、\\(...\\) 行内公式。"""
    from app.services.math_tokenizer import split_inline_math

    nodes: list[dict[str, Any]] = []
    for seg in split_inline_math(text):
        if seg.kind == "inline":
            nodes.append({"type": "mathInline", "attrs": {"latex": seg.latex}})
        elif seg.value:
            nodes.extend(_parse_inline_bold(seg.value))
    if not nodes:
        nodes.append({"type": "text", "text": text or ""})
    return nodes


def markdown_body_to_tiptap_blocks(body: str) -> list[dict[str, Any]]:
    from app.services.math_tokenizer import tokenize_math_in_markdown
    from app.services.repair_inline_math import repair_fragmented_inline_math

    segments = tokenize_math_in_markdown(repair_fragmented_inline_math(body or ""))
    blocks: list[dict[str, Any]] = []
    for seg in segments:
        if seg.kind == "block":
            blocks.append({"type": "mathBlock", "attrs": {"latex": seg.latex}})
        elif seg.kind == "inline":
            blocks.append({"type": "paragraph", "content": [{"type": "mathInline", "attrs": {"latex": seg.latex}}]})
        elif seg.kind == "text" and seg.value.strip():
            blocks.extend(_markdown_text_to_tiptap_blocks(seg.value))
    if not blocks:
        blocks.append({"type": "paragraph", "content": []})
    return blocks


def _markdown_text_to_tiptap_blocks(body: str) -> list[dict[str, Any]]:
    normalized = normalize_gfm_tables(body or "").replace("\r\n", "\n")
    lines = normalized.split("\n")
    blocks: list[dict[str, Any]] = []
    para_lines: list[str] = []
    bullet_lines: list[str] = []
    ordered_lines: list[str] = []

    def flush_para() -> None:
        t = "\n".join(para_lines).strip()
        para_lines.clear()
        if t:
            block: dict[str, Any] = {"type": "paragraph", "content": _parse_paragraph_inline(t)}
            if CAPTION_LINE_RE.match(t):
                block["attrs"] = {"textAlign": "center"}
            blocks.append(block)

    def flush_bullets() -> None:
        if not bullet_lines:
            return
        blocks.append(
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": _parse_paragraph_inline(
                                    re.sub(r"^\s*[-*]\s+", "", raw).strip()
                                ),
                            }
                        ],
                    }
                    for raw in bullet_lines
                ],
            }
        )
        bullet_lines.clear()

    def flush_ordered() -> None:
        if not ordered_lines:
            return
        blocks.append(
            {
                "type": "orderedList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": _parse_paragraph_inline(
                                    re.sub(r"^\s*\d+\.\s+", "", raw).strip()
                                ),
                            }
                        ],
                    }
                    for raw in ordered_lines
                ],
            }
        )
        ordered_lines.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        if TABLE_ROW_RE.match(line):
            flush_para()
            flush_bullets()
            flush_ordered()
            table_node, i = _parse_table_rows(lines, i)
            if table_node:
                blocks.append(table_node)
            continue
        if not line.strip():
            flush_para()
            flush_bullets()
            flush_ordered()
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", line):
            flush_para()
            flush_ordered()
            bullet_lines.append(line)
            i += 1
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            flush_para()
            flush_bullets()
            ordered_lines.append(line)
            i += 1
            continue
        hm = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if hm:
            flush_para()
            flush_bullets()
            flush_ordered()
            level = min(6, len(hm.group(1)))
            blocks.append(
                {
                    "type": "heading",
                    "attrs": {"level": level},
                    "content": _parse_inline_bold(hm.group(2).strip()),
                }
            )
            i += 1
            continue
        flush_bullets()
        flush_ordered()
        para_lines.append(line)
        i += 1

    flush_para()
    flush_bullets()
    flush_ordered()
    if not blocks:
        blocks.append({"type": "paragraph", "content": []})
    return blocks


def make_heading_block(title: str, level: int, anchor_id: str) -> dict[str, Any]:
    return {
        "type": "heading",
        "attrs": {"level": level, "id": anchor_id},
        "content": _parse_inline_bold(title.strip()),
    }
