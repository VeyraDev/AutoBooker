"""Strip LLM decorative Markdown that breaks chapter body rendering."""

from __future__ import annotations

import re

_HR_LINE_RE = re.compile(r"^\s*(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$")
_BLOCKQUOTE_PREFIX_RE = re.compile(r"^(\s*)(?:>|＞|&gt;)\s?")
# Preserve figure/screenshot placeholders; strip other [title] wrappers.
_KEEP_BRACKET_TAG_RE = re.compile(r"^\[(DIAGRAM|SCREENSHOT|FLOWCHART|CHART)\s*:", re.I)
_BRACKET_TITLE_RE = re.compile(r"^[\[【]([^\[\]【】]{1,120})[\]】]\s*$")
_MARKDOWN_BRACKET_HEADING_RE = re.compile(
    r"^(\s*#{1,6}\s+)[\[【]([^\[\]【】]{1,120})[\]】](\s*)$"
)
_INLINE_EMPTY_BRACKETS_RE = re.compile(r"\[\s*\]")
_NUMERIC_REFERENCE_RE = re.compile(r"^\d+(?:\s*[-,，]\s*\d+)*$")


def sanitize_chapter_markdown(raw: str) -> str:
    """Normalize common model artifacts before TipTap conversion.

    - Standalone ``---`` / ``***`` / ``___`` -> blank line (not HR)
    - Leading ``>`` / ``＞`` blockquote markers -> removed
    - Outline-style ``[标题]`` / ``【标题】`` lines -> bare title
    - Keep ``[DIAGRAM:…]`` / ``[SCREENSHOT:…]``
    """
    text = (raw or "").replace("\r\n", "\n")
    out: list[str] = []
    for line in text.split("\n"):
        if _HR_LINE_RE.match(line):
            out.append("")
            continue
        cleaned = line
        while True:
            m = _BLOCKQUOTE_PREFIX_RE.match(cleaned)
            if not m:
                break
            cleaned = m.group(1) + cleaned[m.end() :]
        stripped = cleaned.strip()
        if stripped and not _KEEP_BRACKET_TAG_RE.match(stripped):
            hm = _MARKDOWN_BRACKET_HEADING_RE.match(cleaned)
            bm = _BRACKET_TITLE_RE.match(stripped)
            if hm and not _NUMERIC_REFERENCE_RE.fullmatch(hm.group(2).strip()):
                cleaned = f"{hm.group(1)}{hm.group(2).strip()}{hm.group(3)}"
            elif bm and not _NUMERIC_REFERENCE_RE.fullmatch(bm.group(1).strip()):
                cleaned = bm.group(1).strip()
            else:
                cleaned = _INLINE_EMPTY_BRACKETS_RE.sub("", cleaned)
        out.append(cleaned)
    joined = "\n".join(out)
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip("\n") + ("\n" if joined.endswith("\n") else "")
