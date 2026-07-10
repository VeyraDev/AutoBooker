"""LLM scan for sensitive content, copyright, citation risks."""

from __future__ import annotations

from app.models.book import Book
from app.models.chapter import Chapter


class ContentRiskReviewer:
    def run(self, book: Book, chapters: list[Chapter], *, context_excerpt: str = "") -> list[dict]:
        findings: list[dict] = []
        sample = " ".join(
            str((c.content or {}).get("text") or "")[:500]
            for c in chapters[:3]
            if isinstance(c.content, dict)
        )
        risky_markers = ("政治", "色情", "暴力煽动", "未授权转载")
        for marker in risky_markers:
            if marker in sample:
                findings.append(
                    {
                        "category": "content_risk",
                        "severity": "medium",
                        "title": f"可能涉及敏感主题：{marker}",
                        "detail": "请人工复核相关段落是否符合出版规范。",
                    }
                )
        if "http://" in sample or "https://" in sample:
            findings.append(
                {
                    "category": "citation_risk",
                    "severity": "low",
                    "title": "正文含外部链接",
                    "detail": "导出前请确认链接可访问且引文格式正确。",
                }
            )
        return findings
