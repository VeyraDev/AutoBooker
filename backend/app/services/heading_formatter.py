"""Map outline section titles to TipTap heading levels (publication hierarchy)."""

from __future__ import annotations

import re

_DIGITS = "零一二三四五六七八九"
_LEGACY_SECTION_RE = re.compile(r"^\d+\.(\d+)\s*(.*)$", re.DOTALL)
_SECTION_PREFIX_RE = re.compile(r"^第[一二三四五六七八九十百千\d]+节")


def section_anchor_id(chapter_index: int, section_index: int) -> str:
    return f"sec-{chapter_index}-{section_index}"


def int_to_cn(n: int) -> str:
    """1→一，10→十，11→十一；百以上回退阿拉伯数字。"""
    if n <= 0:
        return str(n)
    if n < 10:
        return _DIGITS[n]
    if n == 10:
        return "十"
    if n < 20:
        return "十" + (_DIGITS[n % 10] if n % 10 else "")
    if n < 100:
        tens, ones = divmod(n, 10)
        s = _DIGITS[tens] + "十"
        if ones:
            s += _DIGITS[ones]
        return s
    return str(n)


def section_label(section_index: int) -> str:
    """节序号 → 「第一节」「第二节」。"""
    return f"第{int_to_cn(section_index)}节"


def normalize_section_title(title: str, section_index: int) -> str:
    """
    将大纲 legacy 编号（1.1、3.2）转为「第X节」；已有「第X节」前缀则保留。
    section_index 为节在本章内的顺序（1-based），legacy 匹配时优先用编号中的节序号。
    """
    t = (title or "").strip()
    if not t:
        return section_label(section_index)
    m = _LEGACY_SECTION_RE.match(t)
    if m:
        si = int(m.group(1))
        body = m.group(2).strip()
        label = section_label(si)
        return f"{label} {body}".strip() if body else label
    if _SECTION_PREFIX_RE.match(t):
        return t
    return t


def normalize_outline_sections(sections: list[dict]) -> list[dict]:
    """批量规范化大纲 sections 的 title。"""
    out: list[dict] = []
    for i, sec in enumerate(sections):
        if not isinstance(sec, dict):
            continue
        row = dict(sec)
        row["title"] = normalize_section_title(str(row.get("title") or ""), i + 1)
        out.append(row)
    return out


def section_heading_level(title: str) -> int:
    """
    第X节 → 2；一、 → 3；（一）→ 4；1．/1. → 5；（1）→ 6；其余默认 2。
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
    # legacy 大纲编号 1.1 / 2.3（须在纯数字规则之前）
    if re.match(r"^\d+\.\d+", t):
        return 2
    if re.match(r"^\d+[．.]", t):
        return 5
    if re.match(r"^（\s*\d+\s*）", t) or re.match(r"^\(\s*\d+\s*\)", t):
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
    for prefix in ("###### ", "##### ", "#### ", "### ", "## ", "# "):
        if first == prefix + title or first.endswith(title) and first.startswith("#"):
            return "\n".join(lines[1:]).lstrip("\n")
    return body
