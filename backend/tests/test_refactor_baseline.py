"""Refactor baseline snapshots: BookStatus, workflow_mode, review API contracts."""

from __future__ import annotations

from pathlib import Path

from app.models.book import BookStatus, BookWorkflowMode


def test_book_status_enum_snapshot():
    assert [s.value for s in BookStatus] == [
        "setup",
        "outline_generating",
        "outline_ready",
        "auto_generating",
        "writing",
        "review_ready",
        "completed",
    ]


def test_book_workflow_mode_enum_snapshot():
    assert [m.value for m in BookWorkflowMode] == ["from_scratch", "optimize_existing"]


def test_review_router_has_no_export_gate_fields():
    review_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "review.py"
    source = review_path.read_text(encoding="utf-8")
    forbidden = ("can_export", "blocking_findings", "must_fix_before_export")
    for token in forbidden:
        assert token not in source
