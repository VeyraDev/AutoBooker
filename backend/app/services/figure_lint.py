"""图表质量程序化检测。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.models.figure import Figure
from app.services.review_anchor import locate_issue_anchor
from app.services.review_scoring import SEVERITY_DEFAULT_PENALTY, standardize_issue

_FIGURE_REF_RE = re.compile(r"(?:图|表)\s*([0-9一二三四五六七八九十]+[-－—.][0-9一二三四五六七八九十]+|[0-9一二三四五六七八九十]+)")
_TABLE_RE = re.compile(r"(?m)^\|.+\|\s*\n^\|(?:\s*:?-{3,}:?\s*\|)+")
_NUMERIC_RE = re.compile(r"\d+(?:\.\d+)?")
_UNIT_HINT_RE = re.compile(r"(单位|%|％|元|美元|小时|分钟|天|年|次|人|kg|g|m|cm|mm|GB|MB|ms|s)")


def lint_figures(md: str, figures: list[Figure] | None) -> dict[str, Any]:
    figures = figures or []
    issues: list[dict[str, Any]] = []
    if not figures and not _TABLE_RE.search(md or ""):
        return {
            "dimension": "figure_quality",
            "raw_score": 100,
            "summary": "本章无图表，图表质量维度不适用。",
            "detector": "figure_lint",
            "confidence": 1.0,
            "status": "not_applicable",
            "issues": [],
        }

    seen_numbers: dict[str, int] = {}
    refs = {m.group(1).replace("－", "-").replace("—", "-") for m in _FIGURE_REF_RE.finditer(md or "")}

    for fig in figures:
        number = (fig.figure_number or "").strip()
        caption = (fig.caption or fig.raw_annotation or "").strip()
        quote = _figure_quote(number, caption)
        if not number:
            issues.append(_issue("missing_figure_number", "medium", "图表缺少编号", "该图表缺少 figure_number，正文难以稳定引用。", quote))
        else:
            seen_numbers[number] = seen_numbers.get(number, 0) + 1
            if number not in refs and f"图{number}" not in (md or "") and f"表{number}" not in (md or ""):
                issues.append(_issue("unreferenced_figure", "low", "正文未引用图表", f"图表 {number} 未在正文中被明确引用。", quote))
        if not caption:
            issues.append(_issue("missing_caption", "medium", "图表缺少标题", "该图表没有标题或说明文字。", quote))
        elif not _has_source(caption):
            issues.append(_issue("missing_figure_source", "medium", "图表缺少来源", "图表说明中未标注来源或生成依据。", quote))
        if _broken_path(fig):
            issues.append(_issue("broken_image", "high", "图片路径失效", "图表记录包含本地图片路径，但文件不存在。", quote))

    for fig in figures:
        quality_issue = _quality_report_issue(fig, _figure_quote((fig.figure_number or "").strip(), (fig.caption or fig.raw_annotation or "").strip()))
        if quality_issue:
            issues.append(quality_issue)
        semantic_issue = _figure_semantic_alignment_issue(fig, md, _figure_quote((fig.figure_number or "").strip(), (fig.caption or fig.raw_annotation or "").strip()))
        if semantic_issue:
            issues.append(semantic_issue)

    for number, count in seen_numbers.items():
        if number and count > 1:
            issues.append(_issue("duplicate_figure_number", "high", "图表编号重复", f"图表编号 {number} 出现 {count} 次。", f"图{number}"))

    figure_numbers = {n for n in seen_numbers if n}
    for ref in refs:
        if figure_numbers and ref not in figure_numbers:
            loc = locate_issue_anchor(md, quote=f"图{ref}") if f"图{ref}" in (md or "") else locate_issue_anchor(md, quote=f"表{ref}")
            issues.append(
                _issue(
                    "missing_figure_target",
                    "high",
                    "正文引用的图表不存在",
                    f"正文引用了图表 {ref}，但图表库中没有对应编号。",
                    loc.quote or f"图{ref}",
                    paragraph_index=loc.paragraph_index,
                    char_start=loc.char_start,
                    char_end=loc.char_end,
                )
            )

    for m in _TABLE_RE.finditer(md or ""):
        table_text = (md or "")[m.start() : min(len(md or ""), m.start() + 600)]
        if _NUMERIC_RE.search(table_text) and not _UNIT_HINT_RE.search(table_text):
            loc = locate_issue_anchor(md, quote=table_text[:80])
            issues.append(
                _issue(
                    "missing_unit",
                    "low",
                    "表格可能缺少单位",
                    "表格包含数字，但表头或说明中未发现单位提示。",
                    table_text[:160],
                    paragraph_index=loc.paragraph_index,
                    char_start=loc.char_start,
                    char_end=loc.char_end,
                )
            )

    standardized = [standardize_issue(i, detector="figure_lint") for i in issues[:30]]
    penalty = min(45, sum(int(i["penalty"]) for i in standardized))
    score = max(0, 100 - penalty)
    return {
        "dimension": "figure_quality",
        "raw_score": 100,
        "summary": "图表质量检测完成。" if standardized else "图表编号、标题、来源和正文引用未发现明显问题。",
        "detector": "figure_lint",
        "confidence": 0.86,
        "status": "completed",
        "issues": standardized,
        "score_preview": score,
    }


def _issue(
    issue_type: str,
    severity: str,
    title: str,
    explanation: str,
    quote: str,
    *,
    paragraph_index: int | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
    quality_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = {
        "dimension": "figure_quality",
        "issue_type": issue_type,
        "severity": severity,
        "penalty": SEVERITY_DEFAULT_PENALTY[severity],
        "title": title,
        "explanation": explanation,
        "quote": quote,
        "action": "revise",
        "replacement_text": "",
        "paragraph_index": paragraph_index,
        "char_start": char_start,
        "char_end": char_end,
        "detector": "figure_lint",
        "confidence": 0.82,
    }
    if quality_evidence:
        out["quality_evidence"] = quality_evidence
    return out


def _quality_report_issue(fig: Figure, quote: str) -> dict[str, Any] | None:
    raw = getattr(fig, "classification_json", None)
    clf = raw if isinstance(raw, dict) else {}
    report = clf.get("quality_report")
    if not isinstance(report, dict):
        return None
    status = str(report.get("status") or "")
    failures = [str(x) for x in (report.get("failures") or []) if str(x)]
    warnings = [str(x) for x in (report.get("warnings") or []) if str(x)]
    if status not in {"failed", "warning", "needs_clarification"} and not failures:
        return None
    severity = "high" if status == "failed" or failures else "medium"
    title = "图像生成质量未达标" if severity == "high" else "图像生成质量需要复核"
    explanation = "图像生成链路返回 quality_report，提示语义覆盖、布局或渲染质量存在风险。"
    flags = (failures + warnings)[:8]
    if flags:
        explanation += " flags=" + ", ".join(flags)
    return _issue(
        "figure_quality_report",
        severity,
        title,
        explanation,
        quote,
        quality_evidence=report,
    )


def _figure_quote(number: str, caption: str) -> str:
    if number and caption:
        return f"图{number} {caption[:120]}"
    if number:
        return f"图{number}"
    return caption[:160]


def _has_source(text: str) -> bool:
    t = text.lower()
    return "来源" in text or "资料" in text or "source" in t or "据" in text


def _figure_semantic_alignment_issue(fig: Figure, md: str, quote: str) -> dict[str, Any] | None:
    clf = getattr(fig, "classification_json", None)
    if not isinstance(clf, dict):
        return None
    semantic_ir = clf.get("semantic_ir")
    if not isinstance(semantic_ir, dict):
        return None
    labels = [str(o.get("name") or "") for o in (semantic_ir.get("objects") or []) if isinstance(o, dict)]
    labels = [x for x in labels if x]
    if not labels or not quote:
        return None
    number = (fig.figure_number or "").strip()
    if not number:
        return None
    ref = f"图{number}"
    if ref not in (md or ""):
        return None
    idx = (md or "").find(ref)
    context = (md or "")[max(0, idx - 120) : min(len(md or ""), idx + 200)]
    matched = [lbl for lbl in labels if lbl in context or lbl in (md or "")]
    if len(matched) >= max(1, len(labels) // 3):
        return None
    loc = locate_issue_anchor(md, quote=ref)
    return _issue(
        "figure_semantic_mismatch",
        "low",
        "正文与图语义可能不一致",
        f"正文引用图 {number}，但图中关键实体（{', '.join(labels[:4])}）未在引用上下文中出现。",
        quote or ref,
        paragraph_index=loc.paragraph_index,
        char_start=loc.char_start,
        char_end=loc.char_end,
        quality_evidence={"figure_labels": labels[:12], "context": context[:200]},
    )


def _broken_path(fig: Figure) -> bool:
    path = (fig.file_path or "").strip()
    if not path:
        return False
    try:
        p = Path(path)
        return p.is_absolute() and not p.exists()
    except OSError:
        return True
