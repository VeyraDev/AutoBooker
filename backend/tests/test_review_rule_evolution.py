"""Tests for controlled review rule evolution candidates."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.models.review_rule_override import ReviewRuleOverride
from app.services.review.review_rule_evolution import (
    build_confirmed_rule_prompt_block,
    build_rule_candidate_prompt_block,
    build_rule_candidates,
    build_rule_feedback_stats,
    decide_rule_candidate,
    restore_review_rule_version,
)


def _chapter_issue(*, status: str = "open", accepted: bool = False, issue_type: str = "generic_summary"):
    return SimpleNamespace(
        status=status,
        applied_at=object() if accepted else None,
        resolved_at=None,
        quality_evidence={"product_dimension": "argument_quality", "fix_capability": "preview_apply"},
        dimension="ai_signature",
        issue_type=issue_type,
        detector="ai_text_risk_reviewer",
        title="总结表达偏空泛",
    )


def test_rule_candidate_promotes_repeatedly_accepted_low_risk_issue():
    stats = build_rule_feedback_stats(
        [
            _chapter_issue(accepted=True),
            _chapter_issue(accepted=True),
            _chapter_issue(status="resolved"),
            _chapter_issue(status="dismissed"),
        ],
        [],
    )

    candidates = build_rule_candidates(stats, min_decided=3)

    assert candidates
    item = candidates[0]
    assert item["recommendation"] == "promote"
    assert item["accepted"] == 3
    assert item["dismissed"] == 1
    assert item["fix_capability"] == "preview_apply"
    assert "候选信号" in item["safety_note"]


def test_rule_candidate_demotes_repeatedly_dismissed_issue():
    stats = build_rule_feedback_stats(
        [
            _chapter_issue(status="dismissed", issue_type="style_preference"),
            _chapter_issue(status="dismissed", issue_type="style_preference"),
            _chapter_issue(status="dismissed", issue_type="style_preference"),
            _chapter_issue(accepted=True, issue_type="style_preference"),
        ],
        [],
    )

    candidates = build_rule_candidates(stats, min_decided=3)

    assert candidates[0]["recommendation"] == "demote"
    assert candidates[0]["dismissal_rate"] >= 0.6
    assert "更强证据" in candidates[0]["reason"]


def test_rule_candidate_prompt_block_is_explicitly_non_authoritative():
    block = build_rule_candidate_prompt_block(
        [
            {
                "recommendation": "demote",
                "product_dimension": "language_credibility",
                "issue_type": "style_preference",
                "fix_capability": "observe_only",
                "accepted": 1,
                "dismissed": 4,
                "reason": "同类建议多次被拒绝。",
            }
        ]
    )

    assert "审校规则候选反馈" in block
    assert "不是正式规则" in block
    assert "不能替代原文依据" in block
    assert "应降低打扰" in block


def test_confirmed_rule_prompt_block_marks_rules_as_user_confirmed_and_project_scoped():
    block = build_confirmed_rule_prompt_block(
        [
            {
                "version": 2,
                "product_dimension": "language_credibility",
                "issue_type": "paragraph_echo",
                "rule_text": "同一小节重复绕回同一结论时，应优先合并重复表达。",
            }
        ]
    )

    assert "已确认项目审校规则" in block
    assert "用户人工确认" in block
    assert "仅作用于本书项目" in block
    assert "不得替代事实核验" in block
    assert "v2 language_credibility / paragraph_echo" in block
    assert "优先合并重复表达" in block


def test_restore_review_rule_version_creates_new_active_version_and_archives_current():
    book_id = uuid4()
    user_id = uuid4()
    candidate_id = "rule_candidate:language_credibility:paragraph_echo:preview_apply"
    source = ReviewRuleOverride(
        id=uuid4(),
        book_id=book_id,
        candidate_id=candidate_id,
        version=1,
        status="archived",
        recommendation="promote",
        product_dimension="language_credibility",
        issue_type="paragraph_echo",
        fix_capability="preview_apply",
        detector="ai_text_risk_reviewer",
        rule_text="旧版规则文本",
        source_stats_json={"accepted": 4},
    )
    active = ReviewRuleOverride(
        id=uuid4(),
        book_id=book_id,
        candidate_id=candidate_id,
        version=2,
        status="active",
        recommendation="promote",
        product_dimension="language_credibility",
        issue_type="paragraph_echo",
        fix_capability="preview_apply",
        detector="ai_text_risk_reviewer",
        rule_text="新版规则文本",
    )
    db = _FakeDb(
        [
            _FakeQuery(first_value=source),
            _FakeQuery(all_value=[active]),
            _FakeQuery(first_value=active),
        ]
    )

    restored = restore_review_rule_version(
        db,  # type: ignore[arg-type]
        book_id=book_id,
        user_id=user_id,
        rule_id=source.id,
        decision_note="恢复旧规则",
    )

    assert active.status == "archived"
    assert restored.status == "active"
    assert restored.version == 3
    assert restored.rule_text == "旧版规则文本"
    assert restored.decision_note == "恢复旧规则"
    assert restored.created_by == user_id
    assert restored.source_stats_json["restored_from_rule_id"] == str(source.id)
    assert restored.source_stats_json["restored_from_version"] == 1
    assert restored.source_stats_json["regression_gate"]["status"] == "passed"
    assert db.added == [restored]


def test_decide_rule_candidate_active_stores_regression_gate_result():
    book_id = uuid4()
    user_id = uuid4()
    finding = SimpleNamespace(
        source_ref_json={"product_dimension": "structure_progress", "fix_capability": "preview_apply"},
        status="resolved",
        track="",
        category="paragraph_echo",
        title="段落绕回同一结论",
    )
    db = _FakeDb(
        [
            _FakeQuery(all_value=[]),
            _FakeQuery(all_value=[finding, finding, finding]),
            _FakeQuery(all_value=[]),
            _FakeQuery(first_value=None),
            _FakeQuery(all_value=[]),
        ]
    )

    row = decide_rule_candidate(
        db,  # type: ignore[arg-type]
        book_id=book_id,
        user_id=user_id,
        candidate_id="rule_candidate:structure_progress:paragraph_echo:preview_apply",
        decision="active",
        decision_note="确认规则",
        rule_text="同一小节重复绕回同一结论时，应优先提示合并重复表达。",
    )

    assert row.status == "active"
    assert row.version == 1
    assert row.source_stats_json["regression_gate"]["status"] == "passed"
    assert row.source_stats_json["regression_gate"]["coverage_status"] == "direct"
    assert db.added == [row]


class _FakeQuery:
    def __init__(self, *, first_value=None, all_value=None):
        self.first_value = first_value
        self.all_value = all_value or []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_value

    def all(self):
        return self.all_value


class _FakeDb:
    def __init__(self, queries):
        self.queries = list(queries)
        self.added = []

    def query(self, *args, **kwargs):
        return self.queries.pop(0)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        return None
