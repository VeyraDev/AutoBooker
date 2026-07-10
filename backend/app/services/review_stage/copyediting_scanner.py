"""Rule-based copyediting candidate recall."""

from __future__ import annotations

import re

from app.models.chapter import Chapter

_COPY_PATTERNS = [
    (re.compile(r"的的"), "重复助词「的的」"),
    (re.compile(r"。。+"), "连续句号"),
    (re.compile(r"\s{3,}"), "异常空白"),
]


class CopyeditingScanner:
    def run(self, chapters: list[Chapter]) -> list[dict]:
        findings: list[dict] = []
        for ch in chapters:
            text = ""
            if isinstance(ch.content, dict):
                text = str(ch.content.get("text") or "")
            for pattern, label in _COPY_PATTERNS:
                if pattern.search(text):
                    findings.append(
                        {
                            "category": "copyediting",
                            "severity": "low",
                            "title": f"第{ch.index}章可能存在排版问题",
                            "detail": label,
                        }
                    )
                    break
        return findings[:20]
