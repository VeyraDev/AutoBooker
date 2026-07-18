"""Regression gate for project-level review rule changes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.review.review_finding_validator import validate_finding


_ISSUE_AREA_MAP: dict[str, str] = {
    "paragraph_echo": "paragraph_echo",
    "paragraph_adjacent_echo": "paragraph_echo",
    "paragraph_near_duplicate": "paragraph_echo",
    "repeated_skeleton": "paragraph_echo",
    "generic_summary": "ai_text_risk",
    "template_connector": "ai_text_risk",
    "unsupported_generic_claim": "reference_authenticity",
    "missing_citation": "reference_authenticity",
    "reference_missing_abstract": "reference_authenticity",
    "source_mismatch": "reference_authenticity",
    "figure_table_numbering": "layout_format",
    "first_line_indent": "layout_format",
    "title_marketing_or_too_long": "title_quality",
    "title_abstract_only": "title_quality",
    "undefined_theory_term": "title_quality",
    "logic_jump": "content_logic",
}

_DIMENSION_AREA_MAP: dict[str, str] = {
    "evidence_citation": "reference_authenticity",
    "publication_delivery": "layout_format",
    "structure_progress": "paragraph_echo",
    "argument_quality": "ai_text_risk",
    "goal_alignment": "title_quality",
}


def run_review_rule_regression_gate(
    *,
    rule_candidate: dict[str, Any],
    rule_text: str,
    cases_path: Path | None = None,
    assertions_path: Path | None = None,
) -> dict[str, Any]:
    cases_file = cases_path or _default_cases_path()
    assertions_file = assertions_path or _default_assertions_path()
    if not cases_file.exists():
        return {
            "status": "failed",
            "coverage_status": "missing_testset",
            "blocked_reason": f"review quality fixture not found: {cases_file}",
            "passed_case_ids": [],
            "failed_case_ids": [],
            "warnings": [],
            "conflicts": [],
        }

    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    machine_assertions = {}
    if assertions_file and assertions_file.exists():
        machine_assertions = json.loads(assertions_file.read_text(encoding="utf-8"))

    failures: list[dict[str, str]] = []
    passed_case_ids: list[str] = []
    for case in cases:
        if not case.get("auto_runnable") or not case.get("candidate_finding"):
            continue
        ok, reason = _run_auto_case(case)
        if ok:
            passed_case_ids.append(str(case.get("id")))
        else:
            failures.append({"case_id": str(case.get("id")), "reason": reason})

    related_area = _rule_area(rule_candidate)
    related_cases = [case for case in cases if case.get("area") == related_area] if related_area else []
    conflicts = _contract_conflicts(rule_candidate, rule_text)

    warnings: list[str] = []
    if not related_cases:
        warnings.append("当前规则没有直接命中的审校 fixture，已仅执行核心自动断言。")

    status = "passed"
    blocked_reason = ""
    if failures:
        status = "failed"
        blocked_reason = "审校测试集自动断言失败。"
    if conflicts:
        status = "failed"
        blocked_reason = "规则文本或修复能力与审校测试集契约冲突。"

    return {
        "status": status,
        "coverage_status": "direct" if related_cases else "none",
        "blocked_reason": blocked_reason,
        "case_count": len(cases),
        "auto_case_count": len(passed_case_ids) + len(failures),
        "related_area": related_area or "",
        "related_case_ids": [str(case.get("id")) for case in related_cases],
        "passed_case_ids": passed_case_ids,
        "failed_case_ids": [item["case_id"] for item in failures],
        "failures": failures,
        "machine_assertion_count": len(machine_assertions),
        "warnings": warnings,
        "conflicts": conflicts,
    }


def ensure_review_rule_regression_gate_passed(
    *,
    rule_candidate: dict[str, Any],
    rule_text: str,
) -> dict[str, Any]:
    result = run_review_rule_regression_gate(rule_candidate=rule_candidate, rule_text=rule_text)
    if result.get("status") != "passed":
        reason = result.get("blocked_reason") or "review rule regression gate failed"
        raise ValueError(f"review rule regression gate failed: {reason}")
    return result


def _run_auto_case(case: dict[str, Any]) -> tuple[bool, str]:
    expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
    result = validate_finding(case["candidate_finding"], chapter_md=case.get("chapter_md"))

    if expected.get("validator_result") == "drop":
        if result is None:
            return True, ""
        return False, "expected finding to be dropped"

    if result is None:
        return False, "expected finding to be kept"
    if result.get("tier") != expected.get("tier"):
        return False, f"tier mismatch: expected {expected.get('tier')}, got {result.get('tier')}"
    if expected.get("fix_capability") and result.get("fix_capability") != expected.get("fix_capability"):
        return (
            False,
            f"fix_capability mismatch: expected {expected.get('fix_capability')}, got {result.get('fix_capability')}",
        )
    if expected.get("action_option_ids"):
        action_ids = {item.get("id") for item in result.get("action_options", [])}
        missing = set(expected["action_option_ids"]) - action_ids
        if missing:
            return False, f"missing action options: {sorted(missing)}"
    return True, ""


def _rule_area(rule_candidate: dict[str, Any]) -> str:
    issue_type = str(rule_candidate.get("issue_type") or "").strip()
    if issue_type in _ISSUE_AREA_MAP:
        return _ISSUE_AREA_MAP[issue_type]
    product_dimension = str(rule_candidate.get("product_dimension") or "").strip()
    return _DIMENSION_AREA_MAP.get(product_dimension, "")


def _contract_conflicts(rule_candidate: dict[str, Any], rule_text: str) -> list[dict[str, str]]:
    text = rule_text.strip().lower()
    issue_type = str(rule_candidate.get("issue_type") or "").strip().lower()
    product_dimension = str(rule_candidate.get("product_dimension") or "").strip().lower()
    fix_capability = str(rule_candidate.get("fix_capability") or "").strip().lower()
    conflicts: list[dict[str, str]] = []

    if any(token in text for token in ("ai率", "ai 率", "ai百分比", "ai 百分比", "疑似ai生成概率", "疑似 ai 生成概率")):
        conflicts.append(
            {
                "rule_id": "ai.no_ai_rate_percentage.v1",
                "reason": "AI 文本风险不得输出 AI 率、百分比或伪概率结论。",
            }
        )
    if any(token in text for token in ("自动生成参考文献", "自动补造参考文献", "编造参考文献", "补造doi", "生成doi")):
        conflicts.append(
            {
                "rule_id": "reference.no_fabricated_sources.v1",
                "reason": "系统不得自动生成或补造参考文献、DOI、URL 或来源。",
            }
        )
    if ("无定位" in text or "没有定位" in text or "没有原文" in text) and any(
        token in text for token in ("必改", "must_fix", "高风险", "high")
    ):
        conflicts.append(
            {
                "rule_id": "validator.must_fix_requires_location.v1",
                "reason": "没有原文片段或定位的问题不能标为必须修改。",
            }
        )
    if issue_type in {"missing_citation", "reference_missing_abstract", "source_mismatch"} and fix_capability == "preview_apply":
        conflicts.append(
            {
                "rule_id": "reference.verification_not_preview_apply.v1",
                "reason": "引用真实性、缺来源和文献不匹配问题不得直接一键自动修改。",
            }
        )
    if product_dimension == "evidence_citation" and fix_capability == "preview_apply":
        conflicts.append(
            {
                "rule_id": "reference.evidence_requires_choice_or_manual.v1",
                "reason": "事实引用可信度问题默认需要用户选择或人工核验。",
            }
        )
    if issue_type in {"concept_drift", "logic_jump", "undefined_theory_term"} and fix_capability == "preview_apply":
        conflicts.append(
            {
                "rule_id": "content_logic.core_change_not_auto_apply.v1",
                "reason": "核心概念、逻辑跳跃和自造理论问题不得直接一键自动修改。",
            }
        )
    return conflicts


def _default_cases_path() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "review" / "review_quality_cases.json"


def _default_assertions_path() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "审校测试集" / "machine_assertions.json"
        if candidate.exists():
            return candidate
    return None
