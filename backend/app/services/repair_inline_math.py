"""合并被空行/换行拆开的行内公式，避免 Markdown→TipTap 把 $...$ 单独成段。"""

from __future__ import annotations

import re

_INLINE_MATH_ONLY = re.compile(r"^\s*\$(?!\$)(.+?)(?<!\$)\$\s*$")
_HEADING = re.compile(r"^\s*#{1,6}\s")
_BLOCK_MATH = re.compile(r"^\s*\$\$")
_ORPHAN_PUNCT = re.compile(r"^[，。；：、」）\)\]】]")


def repair_fragmented_inline_math(markdown: str) -> str:
    if not markdown or "$" not in markdown:
        return markdown

    lines = markdown.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            if (
                out
                and _INLINE_MATH_ONLY.match(out[-1].strip())
                and i + 1 < len(lines)
                and lines[i + 1].strip()
                and not _HEADING.match(lines[i + 1])
                and not _BLOCK_MATH.match(lines[i + 1])
            ):
                i += 1
                continue
            if (
                out
                and out[-1].strip()
                and not _INLINE_MATH_ONLY.match(out[-1].strip())
                and i + 1 < len(lines)
                and _INLINE_MATH_ONLY.match(lines[i + 1].strip())
            ):
                i += 1
                out[-1] = out[-1].rstrip() + " " + lines[i].strip()
                i += 1
                continue
            out.append(line)
            i += 1
            continue

        if _BLOCK_MATH.match(stripped) or _HEADING.match(stripped):
            out.append(line)
            i += 1
            continue

        if _INLINE_MATH_ONLY.match(stripped):
            if out and out[-1].strip() and not _INLINE_MATH_ONLY.match(out[-1].strip()):
                out[-1] = out[-1].rstrip() + " " + stripped
            elif i + 1 < len(lines) and lines[i + 1].strip() and not _HEADING.match(lines[i + 1]):
                next_stripped = lines[i + 1].strip()
                if not _INLINE_MATH_ONLY.match(next_stripped) and not _BLOCK_MATH.match(next_stripped):
                    out.append(stripped + next_stripped)
                    i += 2
                    continue
                out.append(stripped)
            else:
                out.append(line)
            i += 1
            continue

        if out and _ORPHAN_PUNCT.match(stripped) and out[-1].strip():
            out[-1] = out[-1].rstrip() + stripped
            i += 1
            continue

        out.append(line)
        i += 1

    return "\n".join(out)
