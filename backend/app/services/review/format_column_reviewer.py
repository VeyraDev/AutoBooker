"""Check confirmed format strategy against chapter content."""

from __future__ import annotations

from typing import Any

from app.models.chapter import Chapter
from app.models.book_format_strategy import FormatStrategyStatus
from app.services.citation_service import is_bibliography_chapter


_INSTALL_KEYWORDS = ("安装", "配置", "部署", "setup", "install", "环境")
_TROUBLESHOOT_COLUMNS = ("故障排查", "排错", "troubleshoot", "常见问题")


def _chapter_body(ch: Chapter) -> str:
    if isinstance(ch.content, dict):
        return str(ch.content.get("text") or "")
    return ""


def _suggested_columns(strategy_dict: dict[str, Any] | None, chapter_index: int) -> list[str]:
    if not strategy_dict:
        return []
    suggestions = strategy_dict.get("chapter_suggestions") or {}
    rows = suggestions.get(str(chapter_index)) or []
    names: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            name = str(row.get("column_name") or "").strip()
            if name:
                names.append(name)
    return names


def run_format_column_review(chapters: list[Chapter], context_snapshot: dict[str, Any] | None) -> list[dict]:
    snap = context_snapshot if isinstance(context_snapshot, dict) else {}
    fs = snap.get("format_strategy") if isinstance(snap.get("format_strategy"), dict) else None
    if not fs or fs.get("status") != FormatStrategyStatus.confirmed.value:
        return []

    findings: list[dict] = []
    for ch in chapters:
        if is_bibliography_chapter(ch):
            continue
        title = (ch.title or "").lower()
        summary = (ch.summary or "").lower()
        is_install = any(k.lower() in title or k.lower() in summary for k in _INSTALL_KEYWORDS)
        if not is_install:
            continue

        suggested = _suggested_columns(fs, ch.index)
        has_troubleshoot = any(any(t in s for t in _TROUBLESHOOT_COLUMNS) for s in suggested)
        body = _chapter_body(ch)
        body_has_troubleshoot = any(k in body for k in _TROUBLESHOOT_COLUMNS)

        if has_troubleshoot and not body_has_troubleshoot:
            findings.append(
                {
                    "category": "format_strategy",
                    "severity": "medium",
                    "title": f"第{ch.index}章建议含故障排查类栏目",
                    "detail": f"「{ch.title}」为安装/配置类章节，栏目策略建议包含故障排查，但正文尚未体现相关结构。",
                    "suggestion": "补充常见问题、排错步骤或注意事项，或确认本章不需要故障排查栏目。",
                    "chapter_index": ch.index,
                }
            )
    return findings[:20]
