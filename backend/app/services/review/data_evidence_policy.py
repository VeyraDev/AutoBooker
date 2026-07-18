"""Constants and helpers for data/evidence review findings."""

from __future__ import annotations

from typing import Any

# 具体数据 / 事实 / 案例类问题：默认待核实，不直接升为 must_fix
DATA_EVIDENCE_ISSUE_TYPES = frozenset(
    {
        "missing_citation",
        "unsupported_claim",
        "unsupported_assertion",
        "specific_claim_no_source",
        "unsourced_statistic",
        "unsourced_case",
        "hallucinated_statistic",
    }
)

DATA_EVIDENCE_DIMENSIONS = frozenset(
    {
        "citation_sources",
        "factual_support",
        "citation",
        "hallucination",
    }
)

DATA_ACTION_OPTIONS: list[dict[str, str]] = [
    {
        "id": "add_source",
        "label": "补充来源",
        "description": "绑定具体报告、机构、年份和页码",
        "action_type": "insert",
        "instruction": (
            "在原文精确数字旁补充可核验来源标注（机构/报告名、年份、页码或 DOI）。"
            "不要改写数字本身；不要用「相当比例」等空泛表述替代。"
        ),
    },
    {
        "id": "mark_estimate",
        "label": "保留为估算",
        "description": "明确说明这是作者经验判断或非统计估计",
        "action_type": "revise",
        "instruction": (
            "保留论述意图，但把精确比例改为带有「据作者经验估算／非正式统计」等限定语的表述，"
            "使读者明白这不是已核验的官方统计。禁止改成「相当比例」「同样不低」等空洞套话。"
        ),
    },
    {
        "id": "remove_number",
        "label": "删除数字",
        "description": "数字无法核实时，改写为不依赖精确比例的表述",
        "action_type": "revise",
        "instruction": (
            "删除无法核验的精确比例或统计数字，改用可观察的现象或定性描述完成同一论点。"
            "禁止用「相当比例」「不少」「同样不低」等空泛词填空；保持信息密度。"
        ),
    },
]


def is_data_evidence_issue(finding: dict[str, Any]) -> bool:
    issue_type = str(finding.get("issue_type") or finding.get("category") or "").strip().lower()
    dimension = str(finding.get("dimension") or "").strip().lower()
    product = str(finding.get("product_dimension") or "").strip().lower()
    if issue_type in DATA_EVIDENCE_ISSUE_TYPES:
        return True
    if dimension in DATA_EVIDENCE_DIMENSIONS:
        return True
    if product == "evidence_citation" and issue_type in {
        "missing_citation",
        "unsupported_claim",
        "unsupported_assertion",
        "broken_reference",
    }:
        return True
    title = str(finding.get("title") or "")
    detail = str(finding.get("detail") or finding.get("explanation") or "")
    blob = f"{title} {detail}"
    markers = ("具体比例", "缺少来源", "无来源", "缺少可核验", "统计数字", "百分比", "断言缺少")
    return any(m in blob for m in markers)


def should_elevate_data_to_must_fix(finding: dict[str, Any]) -> bool:
    """仅在明确升格信号下，才把数据来源问题升为必须处理。"""
    if finding.get("elevate_to_must_fix") is True:
        return True
    if finding.get("core_argument_evidence") is True:
        return True
    if finding.get("user_requires_sourced_stats") is True:
        return True
    if finding.get("legal_or_decision_risk") is True:
        return True
    flags = finding.get("priority_flags") or {}
    if isinstance(flags, dict):
        for key in (
            "core_argument_evidence",
            "user_requires_sourced_stats",
            "publication_standard_requires_source",
            "legal_or_decision_risk",
        ):
            if flags.get(key):
                return True
    return False


def default_data_action_options() -> list[dict[str, str]]:
    return [dict(x) for x in DATA_ACTION_OPTIONS]
