"""Split streamed chapter Markdown by heading hierarchy; align bodies to outline section titles."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.heading_formatter import (
    normalize_outline_sections,
    section_anchor_id,
    section_heading_level,
    strip_duplicate_section_title_line,
)
from app.services.chapter_markdown_sanitize import sanitize_chapter_markdown
from app.services.markdown_to_tiptap import make_heading_block, markdown_body_to_tiptap_blocks
from app.services.tiptap_convert import tiptap_json_to_markdown

logger = logging.getLogger(__name__)

HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def compute_section_word_budgets(
    sections: list[dict[str, Any]],
    chapter_total_words: int,
) -> list[int]:
    n = max(len(sections), 1)
    if not sections:
        return [chapter_total_words]
    weights = [max(len(str(s.get("summary") or "")), 20) for s in sections]
    total_w = sum(weights)
    budgets = [max(200, int(chapter_total_words * w / total_w)) for w in weights]
    diff = chapter_total_words - sum(budgets)
    if diff != 0 and budgets:
        budgets[-1] = max(200, budgets[-1] + diff)
    return budgets


def strip_echoed_heading_lines(body: str, section_title: str) -> str:
    """Remove body lines that repeat the section title as Markdown headings."""
    body = strip_duplicate_section_title_line(body, section_title)
    if not body or not section_title:
        return body
    title_norm = section_title.strip().rstrip("：:")
    kept: list[str] = []
    for line in body.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        m = HEADING_LINE_RE.match(stripped)
        if m:
            ht = m.group(2).strip().rstrip("：:")
            if ht == title_norm or title_norm in ht or ht in title_norm:
                continue
        kept.append(line)
    return "\n".join(kept).strip()


def markdown_hashes_for_title(title: str) -> str:
    level = section_heading_level(title)
    return "#" * level


def strip_chapter_level_heading(raw: str) -> str:
    """Remove leading # chapter title if the model wrote one."""
    lines = raw.replace("\r\n", "\n").lstrip("\n").split("\n")
    if not lines:
        return raw
    m = HEADING_LINE_RE.match(lines[0].strip())
    if m and len(m.group(1)) == 1:
        return "\n".join(lines[1:]).lstrip("\n")
    return raw


def align_markdown_to_outline(
    raw: str,
    outline_sections: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    """
    Parse full-chapter Markdown by heading levels and map bodies to outline sections.
    Outline titles are authoritative (LLM heading text is discarded).
    """
    text = strip_chapter_level_heading((raw or "").strip())
    n = len(outline_sections)
    if n == 0:
        return [("", text)]

    titles = [str(s.get("title") or f"第{i + 1}节").strip() for i, s in enumerate(outline_sections)]
    levels = [section_heading_level(t) for t in titles]
    bodies: list[list[str]] = [[] for _ in range(n)]
    current = -1
    preamble: list[str] = []

    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        m = HEADING_LINE_RE.match(stripped)
        if m:
            lvl = len(m.group(1))
            matched = False
            for j in range(max(0, current + 1), n):
                if lvl == levels[j]:
                    current = j
                    matched = True
                    break
            if not matched:
                if current >= 0:
                    bodies[current].append(line)
                else:
                    preamble.append(line)
            continue

        normalized_line = stripped.rstrip("：:")
        direct_match = next(
            (
                j
                for j in range(max(0, current + 1), n)
                if normalized_line == titles[j].strip().rstrip("：:")
            ),
            None,
        )
        if direct_match is not None:
            current = direct_match
            continue

        if current < 0:
            preamble.append(line)
        else:
            bodies[current].append(line)

    out: list[tuple[str, str]] = []
    for i, title in enumerate(titles):
        body = "\n".join(bodies[i]).strip()
        if i == 0 and preamble:
            pre = "\n".join(preamble).strip()
            body = f"{pre}\n\n{body}".strip() if body else pre
        out.append((title, body))
    return out


def rebuild_canonical_markdown(sections: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for title, body in sections:
        if title:
            parts.append(f"{markdown_hashes_for_title(title)} {title}")
        if body.strip():
            parts.append(body.strip())
    return "\n\n".join(parts)


def assemble_chapter_tiptap_from_markdown(
    raw: str,
    *,
    chapter_index: int,
    outline_sections: list[dict[str, Any]],
) -> tuple[dict[str, Any], str, int]:
    """Returns (tiptap_json, canonical_markdown, word_count)."""
    outline_sections = normalize_outline_sections(
        outline_sections if isinstance(outline_sections, list) else []
    )
    aligned = align_markdown_to_outline(raw, outline_sections)
    content: list[dict[str, Any]] = []

    if not outline_sections:
        content.extend(markdown_body_to_tiptap_blocks(strip_chapter_level_heading(raw)))
    else:
        for i, (title, body) in enumerate(aligned):
            level = section_heading_level(title)
            anchor = section_anchor_id(chapter_index, i)
            content.append(make_heading_block(title, level, anchor))
            clean = strip_echoed_heading_lines(body, title)
            content.extend(markdown_body_to_tiptap_blocks(clean))

    doc = {"type": "doc", "content": content}
    md = rebuild_canonical_markdown(aligned) if outline_sections else tiptap_json_to_markdown(doc)
    wc = len(md.replace("\n", "").replace(" ", ""))
    return doc, md, wc


def process_chapter_generation_result(
    raw_llm: str,
    *,
    chapter_index: int,
    outline_sections: list[dict[str, Any]],
) -> tuple[dict[str, Any], str, int]:
    cleaned = sanitize_chapter_markdown(raw_llm)
    try:
        return assemble_chapter_tiptap_from_markdown(
            cleaned,
            chapter_index=chapter_index,
            outline_sections=outline_sections,
        )
    except Exception as e:
        logger.warning("chapter markdown assemble failed, fallback plain: %s", e)
        doc = {
            "type": "doc",
            "content": markdown_body_to_tiptap_blocks(cleaned),
        }
        md = tiptap_json_to_markdown(doc)
        return doc, md, len(md.replace("\n", "").replace(" ", ""))
