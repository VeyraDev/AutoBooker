"""Check the manuscript against confirmed intake and writing-plan constraints."""

from __future__ import annotations

from typing import Any

from app.models.chapter import Chapter


def _chapter_text(chapters: list[Chapter]) -> str:
    chunks: list[str] = []
    for ch in chapters:
        if isinstance(ch.content, dict):
            chunks.append(str(ch.content.get("text") or ""))
    return "\n".join(chunks)


def _rule_text(raw: Any) -> str:
    if isinstance(raw, dict):
        return str(raw.get("writing_effect") or raw.get("input_ref") or raw.get("content") or "").strip()
    return str(raw or "").strip()


def _direct_phrase(raw: Any) -> str:
    text = _rule_text(raw)
    if len(text) <= 80:
        return text
    return ""


class InputAlignmentReviewer:
    """Non-blocking checks that make confirmed user input visible in review."""

    def run(self, chapters: list[Chapter], context_snapshot: dict[str, Any] | None) -> list[dict]:
        snap = context_snapshot if isinstance(context_snapshot, dict) else {}
        manuscript = _chapter_text(chapters)
        findings: list[dict] = []

        for raw in (snap.get("must_avoid") or [])[:20]:
            phrase = _direct_phrase(raw)
            if phrase and phrase in manuscript:
                findings.append(
                    {
                        "category": "input_alignment",
                        "severity": "medium",
                        "title": "正文可能触碰已确认的禁止事项",
                        "detail": f"已确认应避免：{phrase}",
                        "suggestion": "请复核相关章节是否需要改写，或确认该禁止事项已不适用。",
                    }
                )

        for raw in (snap.get("must_keep") or [])[:20]:
            phrase = _direct_phrase(raw)
            if phrase and phrase not in manuscript:
                findings.append(
                    {
                        "category": "input_alignment",
                        "severity": "low",
                        "title": "已确认保留项未在正文中直接出现",
                        "detail": f"已确认应保留：{phrase}",
                        "suggestion": "如果该内容已被改写表达，请人工确认；否则建议补入正文或大纲。",
                    }
                )

        effects = snap.get("intent_effects") or []
        if effects and not manuscript.strip():
            findings.append(
                {
                    "category": "input_alignment",
                    "severity": "low",
                    "title": "输入意图尚无正文可核验",
                    "detail": "已确认的输入影响项需要在正文生成后继续复核。",
                    "suggestion": "生成正文后重新运行审校，以确认输入意图已影响章节内容。",
                }
            )

        return findings[:30]
