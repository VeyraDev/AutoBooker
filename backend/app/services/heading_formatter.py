"""Map outline section titles to TipTap heading levels (publication hierarchy)."""

from __future__ import annotations

import re


def section_anchor_id(chapter_index: int, section_index: int) -> str:
    return f"sec-{chapter_index}-{section_index}"


def section_heading_level(title: str) -> int:
    """
    第X节 → 2；一、 → 3；（一）→ 4；1. → 5；（1）→ 6；其余默认 2。
    """
    t = (title or "").strip()
    if not t:
        return 2
    if re.match(r"^第[一二三四五六七八九十百千\d]+节", t) or re.match(r"^第\s*\d+\s*节", t):
        return 2
    if re.match(r"^（[一二三四五六七八九十]+）", t) or re.match(r"^\([一二三四五六七八九十]+\)", t):
        return 4
    if re.match(r"^[一二三四五六七八九十]+、", t):
        return 3
    # 大纲小节编号 1.1 / 2.3（须在纯 \d+\. 规则之前，避免误判为五级标题）
    if re.match(r"^\d+\.\d+", t):
        return 2
    if re.match(r"^\d+\.", t):
        return 5
    if re.match(r"^（\d+）", t) or re.match(r"^\(\d+\)", t):
        return 6
    if re.match(r"^\d+、", t):
        return 5
    return 2


def strip_duplicate_section_title_line(body: str, section_title: str) -> str:
    """Remove leading line if model echoed the section title."""
    if not body or not section_title:
        return body
    lines = body.replace("\r\n", "\n").split("\n")
    if not lines:
        return body
    first = lines[0].strip()
    title = section_title.strip()
    if first == title or first.rstrip("：:") == title.rstrip("：:"):
        return "\n".join(lines[1:]).lstrip("\n")
    for prefix in ("## ", "### ", "# "):
        if first == prefix + title or first.endswith(title) and first.startswith("#"):
            return "\n".join(lines[1:]).lstrip("\n")
    return body
