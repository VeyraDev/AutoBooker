"""Quality gates and reports for figure generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.figures.intent.evidence_rules import score_candidate_diagrams
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.services.quality import QualityStatus, worst_status

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{1,}|[\u4e00-\u9fff]{2,}|\d+(?:\.\d+)?%?")
_STOPWORDS = {
    "一个",
    "一张",
    "生成",
    "绘制",
    "展示",
    "说明",
    "图中",
    "包含",
    "如下",
    "通过",
    "连接",
    "箭头",
    "左侧",
    "右侧",
    "流程",
    "架构",
    "示意图",
}


@dataclass
class FigureQualityReport:
    status: str = QualityStatus.passed.value
    semantic_score: float = 1.0
    layout_score: float = 1.0
    render_score: float = 1.0
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "semantic_score": round(float(self.semantic_score), 3),
            "layout_score": round(float(self.layout_score), 3),
            "render_score": round(float(self.render_score), 3),
            "failures": list(dict.fromkeys(self.failures)),
            "warnings": list(dict.fromkeys(self.warnings)),
            "recommendations": list(dict.fromkeys(self.recommendations)),
            "evidence": self.evidence,
        }


def intent_candidate_report(ctx: PipelineContext, intent: DiagramIntent) -> dict[str, Any]:
    candidates = score_candidate_diagrams(ctx.normalized_input)
    top = candidates[0] if candidates else {}
    second = candidates[1] if len(candidates) > 1 else {}
    gap = round(float(top.get("score") or 0) - float(second.get("score") or 0), 3) if second else 1.0
    needs_clarification = bool(
        second
        and gap <= 0.12
        and float(top.get("score") or 0) >= 0.45
        and float(getattr(intent, "confidence", 0.0) or 0.0) < 0.9
    )
    return {
        "candidates": candidates,
        "top_candidate": top,
        "second_candidate": second,
        "confidence_gap": gap,
        "needs_clarification": needs_clarification,
    }


def semantic_coverage_report(text: str, semantic_ir: dict[str, Any] | None) -> dict[str, Any]:
    tokens = _important_tokens(text)
    if not tokens:
        return {"score": 1.0, "matched": [], "missing": [], "tokens": []}
    haystack_parts: list[str] = []
    if isinstance(semantic_ir, dict):
        for obj in semantic_ir.get("objects") or []:
            if isinstance(obj, dict):
                haystack_parts.extend([str(obj.get("name") or ""), str(obj.get("kind") or "")])
        for rel in semantic_ir.get("relations") or []:
            if isinstance(rel, dict):
                haystack_parts.extend(str(rel.get(k) or "") for k in ("verb", "label", "from", "to"))
        for evt in semantic_ir.get("events") or []:
            if isinstance(evt, dict):
                haystack_parts.extend(str(evt.get(k) or "") for k in ("type", "sender", "receiver", "channel", "label"))
        haystack_parts.extend(str(x) for x in semantic_ir.get("unknowns") or [])
    haystack = " ".join(haystack_parts).lower()
    matched = [tok for tok in tokens if tok.lower() in haystack or _loose_match(tok, haystack)]
    missing = [tok for tok in tokens if tok not in matched]
    return {
        "score": len(matched) / len(tokens),
        "matched": matched,
        "missing": missing[:12],
        "tokens": tokens[:24],
    }


def initial_quality_report(
    *,
    ctx: PipelineContext,
    intent: DiagramIntent,
    semantic_ir: dict[str, Any] | None = None,
    quality_flags: list[str] | None = None,
    render_warnings: list[str] | None = None,
) -> dict[str, Any]:
    intent_report = intent_candidate_report(ctx, intent)
    coverage = semantic_coverage_report(ctx.normalized_input, semantic_ir)
    failures: list[str] = []
    warnings = list(render_warnings or [])
    recommendations: list[str] = []
    status = QualityStatus.passed.value
    semantic_score = float(coverage["score"])

    if intent_report["needs_clarification"]:
        status = QualityStatus.needs_clarification.value
        warnings.append("intent_candidates_close")
        recommendations.append("请明确希望生成流程、架构、对比、数据图或场景插图。")
    if semantic_ir is not None and semantic_score < 0.35:
        status = QualityStatus.failed.value
        failures.append("semantic_coverage_low")
        recommendations.append("图像描述中的关键实体或关系未进入结构化语义，请补充或重写标注。")
    elif semantic_ir is not None and semantic_score < 0.55:
        status = worst_status(status, QualityStatus.warning)
        warnings.append("semantic_coverage_partial")
        recommendations.append("建议检查图中是否遗漏关键实体或关系。")
    for flag in quality_flags or []:
        if flag in {"missing_nodes", "annotation_node"}:
            status = QualityStatus.failed.value
            failures.append(flag)
        elif flag:
            status = worst_status(status, QualityStatus.warning)
            warnings.append(str(flag))

    return FigureQualityReport(
        status=status,
        semantic_score=semantic_score,
        layout_score=1.0,
        render_score=1.0,
        failures=failures,
        warnings=warnings,
        recommendations=recommendations,
        evidence={
            "intent": intent_report,
            "semantic_coverage": coverage,
        },
    ).to_dict()


def inspect_rendered_figure(
    *,
    png_path: Path | None,
    svg_path: Path | None,
    classification: dict[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []
    render_score = 1.0
    layout_score = 1.0

    has_svg = bool(svg_path and svg_path.is_file())
    if not png_path or not png_path.is_file():
        if has_svg:
            warnings.append("svg_only_no_png")
            render_score = 0.85
        else:
            failures.append("missing_render_asset")
            recommendations.append("未生成 PNG 或 SVG，需检查渲染器返回契约。")
            render_score = 0.0
    else:
        try:
            from PIL import Image

            with Image.open(png_path) as img:
                width, height = img.size
                if width < 320 or height < 240:
                    warnings.append("small_canvas")
                    render_score = min(render_score, 0.75)
                extrema = img.convert("L").getextrema()
                if extrema and extrema[0] == extrema[1]:
                    failures.append("blank_png")
                    render_score = 0.0
        except Exception as exc:
            warnings.append("png_inspection_failed")
            recommendations.append(f"PNG 检查失败: {exc}")
            render_score = min(render_score, 0.6)

    layout_result = classification.get("layout_result") or {}
    if isinstance(layout_result, dict):
        overlap_count = _count_node_overlaps(layout_result)
        if overlap_count:
            failures.append("node_overlap")
            layout_score = 0.0 if overlap_count > 2 else 0.45
            recommendations.append("节点布局存在重叠，请改用分层/蛇形布局或拆分复杂图。")
        label_overflow = _count_label_overflow(classification, layout_result)
        if label_overflow:
            warnings.append("label_overflow_risk")
            layout_score = min(layout_score, 0.7)
            recommendations.append("部分节点文字过长，建议压缩标签或增大节点。")

    status = QualityStatus.passed.value
    if failures:
        status = QualityStatus.failed.value
    elif warnings:
        status = QualityStatus.warning.value
    return FigureQualityReport(
        status=status,
        semantic_score=float((classification.get("quality_report") or {}).get("semantic_score", 1.0)),
        layout_score=layout_score,
        render_score=render_score,
        failures=failures,
        warnings=warnings,
        recommendations=recommendations,
        evidence={
            "png_path": str(png_path) if png_path else "",
            "svg_path": str(svg_path) if svg_path else "",
        },
    ).to_dict()


def merge_quality_reports(*reports: dict[str, Any] | None) -> dict[str, Any]:
    out = FigureQualityReport().to_dict()
    statuses: list[str] = []
    for report in reports:
        if not isinstance(report, dict):
            continue
        statuses.append(str(report.get("status") or QualityStatus.passed.value))
        for key in ("semantic_score", "layout_score", "render_score"):
            out[key] = min(float(out.get(key, 1.0)), float(report.get(key, 1.0)))
        for key in ("failures", "warnings", "recommendations"):
            out[key] = list(dict.fromkeys(list(out.get(key) or []) + list(report.get(key) or [])))
        evidence = out.setdefault("evidence", {})
        for k, v in dict(report.get("evidence") or {}).items():
            evidence[k] = v
    out["status"] = worst_status(*statuses)
    return out


def _important_tokens(text: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(str(text or "")):
        tok = raw.strip(" ，,。；;：:（）()[]【】")
        if len(tok) < 2 or tok in _STOPWORDS or tok.lower() in _STOPWORDS:
            continue
        if re.fullmatch(r"\d+", tok) and len(tok) < 4:
            continue
        if tok not in seen:
            seen.add(tok)
            tokens.append(tok)
    return tokens


def _loose_match(token: str, haystack: str) -> bool:
    if len(token) <= 3:
        return token.lower() in haystack
    return any(token[i : i + 3].lower() in haystack for i in range(0, len(token) - 2))


def _count_node_overlaps(layout_result: dict[str, Any]) -> int:
    positions = [p for p in (layout_result.get("node_positions") or {}).values() if isinstance(p, dict)]
    count = 0
    for i, a in enumerate(positions):
        for b in positions[i + 1 :]:
            if not (
                float(a.get("x", 0)) + float(a.get("width", 0)) <= float(b.get("x", 0))
                or float(b.get("x", 0)) + float(b.get("width", 0)) <= float(a.get("x", 0))
                or float(a.get("y", 0)) + float(a.get("height", 0)) <= float(b.get("y", 0))
                or float(b.get("y", 0)) + float(b.get("height", 0)) <= float(a.get("y", 0))
            ):
                count += 1
    return count


def _count_label_overflow(classification: dict[str, Any], layout_result: dict[str, Any]) -> int:
    parsed = classification.get("parsed_spec") or {}
    nodes = {str(n.get("id")): str(n.get("label") or "") for n in parsed.get("nodes") or [] if isinstance(n, dict)}
    positions = layout_result.get("node_positions") or {}
    overflow = 0
    for nid, label in nodes.items():
        pos = positions.get(nid)
        if not isinstance(pos, dict):
            continue
        width = float(pos.get("width") or 120)
        visual_units = sum(1.0 if "\u4e00" <= ch <= "\u9fff" else 0.55 for ch in label)
        if visual_units * 13 > max(40.0, width * 1.9):
            overflow += 1
    return overflow
