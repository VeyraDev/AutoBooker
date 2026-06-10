"""布局 Critic：layout_result 与 SVG 文本交叉验证。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.services.quality import QualityStatus


def _parse_svg_texts(svg_path: Path | None) -> list[str]:
    if not svg_path or not svg_path.is_file():
        return []
    text = svg_path.read_text(encoding="utf-8", errors="ignore")
    return re.findall(r"<text[^>]*>([^<]+)</text>", text)


def run_layout_critic(
    *,
    layout_result: dict[str, Any] | None,
    svg_path: Path | None = None,
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []
    layout_score = 1.0

    layout_result = layout_result or (classification or {}).get("layout_result") or {}
    positions = [p for p in (layout_result.get("node_positions") or {}).values() if isinstance(p, dict)]

    overlap = 0
    for i, a in enumerate(positions):
        for b in positions[i + 1 :]:
            if not (
                float(a.get("x", 0)) + float(a.get("width", 0)) <= float(b.get("x", 0))
                or float(b.get("x", 0)) + float(b.get("width", 0)) <= float(a.get("x", 0))
                or float(a.get("y", 0)) + float(a.get("height", 0)) <= float(b.get("y", 0))
                or float(b.get("y", 0)) + float(b.get("height", 0)) <= float(a.get("y", 0))
            ):
                overlap += 1

    if overlap:
        warnings.append("node_overlap")
        layout_score = 0.0 if overlap > 2 else 0.45

    svg_labels = _parse_svg_texts(svg_path)
    parsed = (classification or {}).get("parsed_spec") or {}
    expected = [str(n.get("label") or "") for n in (parsed.get("nodes") or []) if isinstance(n, dict)]
    if expected and svg_labels:
        missing = [lbl for lbl in expected if lbl and lbl not in " ".join(svg_labels)]
        if len(missing) > len(expected) * 0.4:
            warnings.append("svg_label_mismatch")
            layout_score = min(layout_score, 0.65)

    status = QualityStatus.warning.value if warnings else QualityStatus.passed.value

    return {
        "status": status,
        "layout_score": round(layout_score, 3),
        "failures": failures,
        "warnings": warnings,
        "recommendations": recommendations,
        "evidence": {"overlap_count": overlap, "svg_text_count": len(svg_labels)},
    }
