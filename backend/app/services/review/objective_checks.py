"""Objective publication checks — reuse publication modules + public_rules seed."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.services.review.review_rule_library import load_public_rules
from app.services.review_stage.input_alignment_reviewer import InputAlignmentReviewer
from app.services.review_stage.export_structure_reviewer import ExportStructureReviewer
from app.services.review_stage.copyediting_scanner import CopyeditingScanner
from app.services.review_stage.content_risk_reviewer import ContentRiskReviewer
from app.services.citation_service import is_bibliography_chapter


def _chapter_text(ch: Chapter) -> str:
    if isinstance(ch.content, dict):
        return str(ch.content.get("text") or "")
    return ""


def _check_empty_sections(chapters: list[Chapter]) -> list[dict]:
    findings: list[dict] = []
    heading_re = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
    for ch in chapters:
        if is_bibliography_chapter(ch):
            continue
        body = _chapter_text(ch)
        if not body.strip():
            continue
        headings = heading_re.findall(body)
        for h in headings[:30]:
            pattern = re.compile(rf"^#+\s*{re.escape(h.strip())}\s*$[\s\S]*?(?=^#+\s|\Z)", re.MULTILINE)
            m = pattern.search(body)
            if m and len(m.group(0).strip().splitlines()) <= 1:
                heading_quote = m.group(0).strip()
                findings.append(
                    {
                        "category": "export_structure",
                        "severity": "medium",
                        "title": f"第{ch.index}章存在空节",
                        "detail": f"小节「{h.strip()}」仅有标题无正文。",
                        "suggestion": "补充正文或删除空节标题。",
                        "chapter_index": ch.index,
                        "quote": heading_quote,
                        "rule_id": "no_empty_sections",
                        "book_level": False,
                    }
                )
    return findings[:15]


def _check_figure_numbering(chapters: list[Chapter]) -> list[dict]:
    findings: list[dict] = []
    fig_re = re.compile(r"^图\s*(\d+(?:[-–.]\d+)*)", re.MULTILINE)
    for ch in chapters:
        body = _chapter_text(ch)
        nums = fig_re.findall(body)
        if len(nums) >= 2 and len(set(nums)) != len(nums):
            duplicate = next((num for num in nums if nums.count(num) > 1), nums[0])
            duplicate_match = re.search(rf"^图\s*{re.escape(duplicate)}.*$", body, re.MULTILINE)
            findings.append(
                {
                    "category": "export_structure",
                    "severity": "medium",
                    "title": f"第{ch.index}章图编号可能重复",
                    "detail": "检测到重复的图编号，请核对图题与正文引用。",
                    "rule_id": "figure_table_numbering",
                    "chapter_index": ch.index,
                    "quote": duplicate_match.group(0).strip() if duplicate_match else f"图{duplicate}",
                }
            )
    return findings


def run_objective_checks(
    db: Session,
    book: Book,
    chapters: list[Chapter],
    *,
    context_snapshot: dict[str, Any] | None = None,
    context_excerpt: str = "",
) -> list[dict]:
    """Run deterministic checks; returns candidate findings (pre-validator)."""
    snap = context_snapshot if isinstance(context_snapshot, dict) else {}
    content_chapters = [c for c in chapters if not is_bibliography_chapter(c)]
    findings: list[dict] = []

    findings.extend(ExportStructureReviewer(db).run(book, content_chapters))
    findings.extend(ContentRiskReviewer().run(book, content_chapters, context_excerpt=context_excerpt))
    findings.extend(CopyeditingScanner().run(content_chapters))
    findings.extend(InputAlignmentReviewer().run(content_chapters, snap))
    findings.extend(_check_empty_sections(content_chapters))
    findings.extend(_check_figure_numbering(content_chapters))

    public_rules = {r["id"]: r for r in load_public_rules() if r.get("id")}
    for item in findings:
        rid = item.get("rule_id")
        if rid and rid in public_rules:
            item.setdefault("basis_rule_ids", [rid])
            item.setdefault(
                "basis_refs",
                [f"公开出版规则：{public_rules[rid].get('label', rid)}"],
            )

    return findings[:50]
