"""LLM scan for sensitive content, copyright, citation risks."""

from __future__ import annotations

from app.models.book import Book
from app.models.chapter import Chapter
from app.services.review_anchor import parse_paragraphs


class ContentRiskReviewer:
    def run(self, book: Book, chapters: list[Chapter], *, context_excerpt: str = "") -> list[dict]:
        findings: list[dict] = []
        risky_markers = ("政治", "色情", "暴力煽动", "未授权转载")
        for marker in risky_markers:
            matched = None
            matched_chapter = None
            for chapter in chapters:
                text = str((chapter.content or {}).get("text") or "") if isinstance(chapter.content, dict) else ""
                matched = next((paragraph for paragraph in parse_paragraphs(text) if marker in paragraph.text), None)
                if matched:
                    matched_chapter = chapter
                    break
            if matched and matched_chapter:
                findings.append(
                    {
                        "category": "content_risk",
                        "severity": "medium",
                        "title": f"可能涉及敏感主题：{marker}",
                        "detail": "请人工复核相关段落是否符合出版规范。",
                        "chapter_index": matched_chapter.index,
                        "quote": matched.text[:500],
                        "paragraph_id": matched.paragraph_id,
                        "paragraph_index": matched.paragraph_index,
                        "char_start": matched.char_start,
                        "char_end": matched.char_end,
                        "detector": "content_risk_reviewer",
                    }
                )
        for chapter in chapters:
            text = str((chapter.content or {}).get("text") or "") if isinstance(chapter.content, dict) else ""
            matched = next(
                (paragraph for paragraph in parse_paragraphs(text) if "http://" in paragraph.text or "https://" in paragraph.text),
                None,
            )
            if not matched:
                continue
            findings.append(
                {
                    "category": "citation_risk",
                    "severity": "low",
                    "title": "正文含外部链接",
                    "detail": "导出前请确认链接可访问且引文格式正确。",
                    "chapter_index": chapter.index,
                    "quote": matched.text[:500],
                    "paragraph_id": matched.paragraph_id,
                    "paragraph_index": matched.paragraph_index,
                    "char_start": matched.char_start,
                    "char_end": matched.char_end,
                    "detector": "content_risk_reviewer",
                }
            )
            break
        return findings
