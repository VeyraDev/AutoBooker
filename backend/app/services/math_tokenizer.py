"""Markdown 公式分隔符识别（与前端 mathTokenizer 对齐）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class MathSegment:
    kind: Literal["text", "inline", "block"]
    value: str = ""
    latex: str = ""


def _is_escaped(src: str, index: int) -> bool:
    bs = 0
    i = index - 1
    while i >= 0 and src[i] == "\\":
        bs += 1
        i -= 1
    return bs % 2 == 1


def _read_until(src: str, start: int, end_seq: str) -> tuple[int, bool]:
    i = start
    while i < len(src):
        if src.startswith(end_seq, i) and not _is_escaped(src, i):
            return i + len(end_seq), True
        i += 1
    return len(src), False


def _normalize_inline_latex(latex: str) -> str:
    """Remove hard line breaks inside inline math (e.g. ``$N\\n(i)$`` from LLM/JSON wrapping)."""
    return re.sub(r"\s*\n+\s*", "", latex or "")


def split_inline_math(text: str) -> list[MathSegment]:
    out: list[MathSegment] = []
    buf = ""
    i = 0

    def flush() -> None:
        nonlocal buf
        if buf:
            out.append(MathSegment(kind="text", value=buf))
            buf = ""

    while i < len(text):
        if text.startswith("\\(", i) and not _is_escaped(text, i):
            end, found = _read_until(text, i + 2, "\\)")
            if found:
                latex = _normalize_inline_latex(text[i + 2 : end - 2].strip())
                if latex:
                    flush()
                    out.append(MathSegment(kind="inline", latex=latex))
                    i = end
                    continue
        if text[i] == "$" and not _is_escaped(text, i) and (i + 1 >= len(text) or text[i + 1] != "$"):
            j = i + 1
            matched = False
            while j < len(text):
                if text[j] == "$" and not _is_escaped(text, j):
                    latex = _normalize_inline_latex(text[i + 1 : j].strip())
                    if latex:
                        flush()
                        out.append(MathSegment(kind="inline", latex=latex))
                        i = j + 1
                        matched = True
                    break
                j += 1
            if matched:
                continue
            buf += text[i]
            i += 1
            continue
        buf += text[i]
        i += 1
    flush()
    return out or [MathSegment(kind="text", value=text)]


def tokenize_math_in_markdown(markdown: str) -> list[MathSegment]:
    src = (markdown or "").replace("\r\n", "\n")
    out: list[MathSegment] = []
    zone = "text"
    fence: str | None = None
    i = 0
    buf = ""

    def flush_text() -> None:
        nonlocal buf
        if not buf:
            return
        # 行内 $...$ 留给段落解析（_parse_paragraph_inline）；此处只切 block 级公式。
        out.append(MathSegment(kind="text", value=buf))
        buf = ""

    while i < len(src):
        if zone == "fenced":
            line_end = src.find("\n", i)
            line = src[i:] if line_end == -1 else src[i:line_end]
            if line.strip() == fence:
                out.append(MathSegment(kind="text", value=buf + line + ("" if line_end == -1 else "\n")))
                buf = ""
                zone = "text"
                fence = None
                i = len(src) if line_end == -1 else line_end + 1
                continue
            buf += line + ("" if line_end == -1 else "\n")
            i = len(src) if line_end == -1 else line_end + 1
            continue

        if zone == "inline_code":
            if src[i] == "`" and not _is_escaped(src, i):
                buf += "`"
                i += 1
                zone = "text"
                continue
            buf += src[i]
            i += 1
            continue

        if src.startswith("```", i):
            flush_text()
            fence = "```"
            zone = "fenced"
            buf = "```"
            i += 3
            continue

        if src[i] == "`" and not _is_escaped(src, i):
            flush_text()
            zone = "inline_code"
            buf = "`"
            i += 1
            continue

        if src.startswith("\\[", i) and not _is_escaped(src, i):
            end, found = _read_until(src, i + 2, "\\]")
            if found:
                latex = src[i + 2 : end - 2].strip()
                if latex:
                    flush_text()
                    out.append(MathSegment(kind="block", latex=latex))
                    i = end
                    continue

        if src.startswith("$$", i) and not _is_escaped(src, i):
            end, found = _read_until(src, i + 2, "$$")
            if found:
                latex = src[i + 2 : end - 2].strip()
                if latex:
                    flush_text()
                    out.append(MathSegment(kind="block", latex=latex))
                    i = end
                    continue

        buf += src[i]
        i += 1

    if zone == "fenced":
        out.append(MathSegment(kind="text", value=buf))
    else:
        flush_text()
    return out or [MathSegment(kind="text", value="")]
