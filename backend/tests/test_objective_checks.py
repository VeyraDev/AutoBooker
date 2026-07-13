"""Tests for objective_checks."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.review.objective_checks import _check_figure_numbering, run_objective_checks


def test_figure_numbering_duplicate_detected():
    ch = SimpleNamespace(
        id=uuid4(),
        index=1,
        title="第一章",
        content={"text": "见图 1-1 说明。\n图1-1 架构\n图1-1 重复"},
    )
    findings = _check_figure_numbering([ch])
    assert len(findings) >= 1
    assert findings[0].get("rule_id") == "figure_table_numbering"


def test_run_objective_checks_empty_chapters():
    book = SimpleNamespace(id=uuid4(), title="书", citation_style=None)
    db = SimpleNamespace(query=lambda *a, **k: SimpleNamespace(filter=lambda *a, **k: SimpleNamespace(all=lambda: [])))
    rows = run_objective_checks(db, book, [], context_snapshot={"must_avoid": []})  # type: ignore[arg-type]
    assert isinstance(rows, list)
