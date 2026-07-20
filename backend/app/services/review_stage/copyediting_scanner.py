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
                match = pattern.search(text)
                if match:
                    findings.append(
                        {
                            "category": "copyediting",
                            "severity": "low",
                            "title": f"第{ch.index}章可能存在排版问题",
                            "detail": label,
                            "chapter_index": ch.index,
                            "quote": match.group(0),
                            "char_start": match.start(),
                            "char_end": match.end(),
                            "detector": "copyediting_scanner",
                        }
                    )
                    break
        return findings[:20]
