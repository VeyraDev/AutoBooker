"""Contract tests for the review quality fixture.

These tests intentionally cover the current validator contract and the fixture
schema. Future detector implementations can consume the same cases and add
stronger assertions without rewriting the test data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services.review.review_finding_validator import validate_finding

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "review" / "review_quality_cases.json"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_REVIEW_TESTSET_ASSERTIONS = _PROJECT_ROOT / "审校测试集" / "machine_assertions.json"

_VALID_AREAS = {
    "title_quality",
    "paragraph_echo",
    "reference_authenticity",
    "layout_format",
    "ai_text_risk",
    "content_logic",
}
_VALID_TIERS = {"must_fix", "suggest", "observe", "needs_verification"}
_VALID_FIX_CAPABILITIES = {"preview_apply", "choice_then_apply", "manual_only", "observe_only"}


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(_FIXTURES.read_text(encoding="utf-8"))


def test_review_quality_cases_schema() -> None:
    cases = _load_cases()
    assert len(cases) >= 10

    ids: set[str] = set()
    areas = {case["area"] for case in cases}
    assert {"title_quality", "paragraph_echo", "reference_authenticity", "layout_format", "ai_text_risk"} <= areas

    for case in cases:
        assert case["id"] not in ids
        ids.add(case["id"])
        assert case["area"] in _VALID_AREAS
        assert case.get("book_style")
        assert isinstance(case.get("auto_runnable"), bool)
        assert "expected" in case

        expected = case["expected"]
        assert expected["tier"] in _VALID_TIERS
        assert expected["fix_capability"] in _VALID_FIX_CAPABILITIES
        assert expected.get("rule_id")
        assert expected.get("reason")

        assert "input" in case or "candidate_finding" in case
        if case["auto_runnable"]:
            assert "candidate_finding" in case


def test_review_testset_machine_assertions_reference_known_cases() -> None:
    cases = _load_cases()
    known_ids = {case["id"] for case in cases}
    assertions = json.loads(_REVIEW_TESTSET_ASSERTIONS.read_text(encoding="utf-8"))

    assert len(assertions) >= 5
    for scenario_id, scenario in assertions.items():
        assert scenario_id.startswith("scenario_")
        assert scenario.get("state_path")
        assert scenario.get("assertions")
        referenced_ids = set(scenario.get("backend_fixture_ids", []))
        assert referenced_ids
        assert referenced_ids <= known_ids


@pytest.mark.parametrize("case", [case for case in _load_cases() if case.get("candidate_finding")])
def test_review_quality_candidate_findings_follow_validator_contract(case: dict[str, Any]) -> None:
    expected = case["expected"]
    result = validate_finding(case["candidate_finding"], chapter_md=case.get("chapter_md"))

    if expected.get("validator_result") == "drop":
        assert result is None
        return

    assert result is not None
    assert result["tier"] == expected["tier"]

    if expected.get("action_option_ids"):
        action_ids = {item.get("id") for item in result.get("action_options", [])}
        assert set(expected["action_option_ids"]) <= action_ids
