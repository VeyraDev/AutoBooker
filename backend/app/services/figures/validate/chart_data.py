"""Chart Data Validator。"""

from __future__ import annotations

from typing import Any


def validate_chart_brief(brief: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    status = str(brief.get("chart_status") or "need_data")
    if status != "ready":
        warnings.append(f"chart_status:{status}")
        return brief, warnings
    cb = brief.get("chart_brief") or {}
    series = cb.get("series") or cb.get("data_points") or []
    values = cb.get("values") or []
    if not series and not values:
        warnings.append("chart_missing_numeric_data")
        brief["chart_status"] = "need_data"
    return brief, warnings
