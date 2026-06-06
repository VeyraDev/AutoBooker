"""Shared quality status helpers for generation/review services."""

from __future__ import annotations

from enum import Enum


class QualityStatus(str, Enum):
    passed = "passed"
    warning = "warning"
    failed = "failed"
    needs_clarification = "needs_clarification"


def worst_status(*statuses: str | QualityStatus | None) -> str:
    order = {
        QualityStatus.passed.value: 0,
        QualityStatus.warning.value: 1,
        QualityStatus.needs_clarification.value: 2,
        QualityStatus.failed.value: 3,
    }
    current = QualityStatus.passed.value
    for raw in statuses:
        val = raw.value if isinstance(raw, QualityStatus) else str(raw or QualityStatus.passed.value)
        if order.get(val, 0) > order.get(current, 0):
            current = val
    return current
