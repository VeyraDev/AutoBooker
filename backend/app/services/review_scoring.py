"""审校维度、issue 标准化与程序化加权评分。"""

from __future__ import annotations

import hashlib
from typing import Any

SCORE_SCHEMA_VERSION = "review_v2"

REVIEW_DIMENSIONS: dict[str, dict[str, Any]] = {
    "logic_structure": {
        "label": "逻辑结构",
        "weight": 15,
        "detector": "review_agent",
    },
    "language_grammar": {
        "label": "语言语法",
        "weight": 15,
        "detector": "review_agent",
    },
    "style_consistency": {
        "label": "风格一致",
        "weight": 10,
        "detector": "review_agent",
    },
    "citation_sources": {
        "label": "引用来源",
        "weight": 20,
        "detector": "citation_lint",
    },
    "factual_support": {
        "label": "事实支撑",
        "weight": 15,
        "detector": "review_agent",
    },
    "figure_quality": {
        "label": "图表质量",
        "weight": 15,
        "detector": "figure_lint",
    },
    "ai_signature": {
        "label": "AI味风险",
        "weight": 10,
        "detector": "ai_detect",
    },
}

DIMENSION_WEIGHTS: dict[str, float] = {
    key: meta["weight"] / 100 for key, meta in REVIEW_DIMENSIONS.items()
}

LEGACY_DIMENSION_MAP: dict[str, str] = {
    "logic": "logic_structure",
    "structure": "logic_structure",
    "grammar": "language_grammar",
    "style": "style_consistency",
    "consistency": "style_consistency",
    "citation": "citation_sources",
    "hallucination": "factual_support",
    "figure": "figure_quality",
    "ai_feature": "ai_signature",
}

CATEGORY_TO_DIMENSION: dict[str, str] = {
    "logic": "logic_structure",
    "structure": "logic_structure",
    "grammar": "language_grammar",
    "style": "style_consistency",
    "consistency": "style_consistency",
    "citation": "citation_sources",
    "hallucination": "factual_support",
    "figure": "figure_quality",
    "code": "logic_structure",
    "other": "language_grammar",
}

SEVERITY_DEFAULT_PENALTY = {
    "high": 10,
    "medium": 6,
    "low": 3,
}

NON_PENALTY_STATUSES = {"resolved", "dismissed", "stale", "failed"}
AVAILABLE_DIMENSION_STATUSES = {"completed", "partial", "not_applicable"}


def clamp_score(raw: Any, default: int = 70) -> int:
    try:
        return max(0, min(100, int(round(float(raw)))))
    except (TypeError, ValueError):
        return default


def normalize_dimension_key(raw: Any) -> str:
    key = str(raw or "").strip().lower()
    return LEGACY_DIMENSION_MAP.get(key, key if key in REVIEW_DIMENSIONS else "language_grammar")


def normalize_dimensions(raw: dict[str, Any] | None) -> dict[str, int]:
    """兼容旧调用：返回固定 7 维原始分。"""
    raw = raw or {}
    out: dict[str, int] = {}
    normalized: dict[str, Any] = {}
    for key, val in raw.items():
        normalized[normalize_dimension_key(key)] = val
    for key in REVIEW_DIMENSIONS:
        val = normalized.get(key, 70)
        if isinstance(val, dict):
            val = val.get("raw_score", val.get("score", 70))
        out[key] = clamp_score(val)
    return out


def compute_overall_score(dimensions: dict[str, Any]) -> int:
    """兼容旧调用：按固定权重计算总分。"""
    rows = []
    for key in REVIEW_DIMENSIONS:
        val = dimensions.get(key, dimensions.get(next((k for k, v in LEGACY_DIMENSION_MAP.items() if v == key), ""), 70))
        if isinstance(val, dict):
            val = val.get("effective_score", val.get("raw_score", val.get("score", 70)))
        rows.append(
            {
                "key": key,
                "effective_score": clamp_score(val),
                "weight": REVIEW_DIMENSIONS[key]["weight"],
                "status": "completed",
            }
        )
    return compute_total_score(rows)


def normalize_agent_dimensions(raw: dict[str, Any] | list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if isinstance(raw, list):
        iterable = [(item.get("key") or item.get("dimension"), item) for item in raw if isinstance(item, dict)]
    elif isinstance(raw, dict):
        iterable = raw.items()
    else:
        iterable = []

    for key_raw, val in iterable:
        key = normalize_dimension_key(key_raw)
        if not isinstance(val, dict):
            val = {"raw_score": val}
        out[key] = {
            "raw_score": clamp_score(val.get("raw_score", val.get("score", 70))),
            "summary": str(val.get("summary") or "")[:500],
            "confidence": _confidence(val.get("confidence"), 0.72),
            "status": str(val.get("status") or "completed"),
            "detector": str(val.get("detector") or REVIEW_DIMENSIONS[key]["detector"]),
        }
    return out


def standardize_issue(raw: dict[str, Any], *, detector: str = "review_agent") -> dict[str, Any]:
    category = str(raw.get("category") or raw.get("dimension") or "other")
    dimension = normalize_dimension_key(raw.get("dimension") or CATEGORY_TO_DIMENSION.get(category, category))
    severity = _enum(str(raw.get("severity") or "medium").lower(), ("high", "medium", "low"), "medium")
    action = _enum(
        str(raw.get("action") or raw.get("action_type") or "revise").lower(),
        ("replace", "delete", "insert", "revise"),
        "revise",
    )
    penalty = raw.get("penalty")
    if penalty is None:
        penalty = SEVERITY_DEFAULT_PENALTY[severity]
    quote = str(raw.get("quote") or "")[:2000]
    title = str(raw.get("title") or "待改进")[:120]
    explanation = str(raw.get("explanation") or raw.get("detail") or "")[:3000]
    replacement = str(raw.get("replacement_text") or raw.get("suggestion") or "")[:4000]
    issue_type = str(raw.get("issue_type") or raw.get("category") or "review_issue").strip() or "review_issue"
    paragraph_index = _optional_int(raw.get("paragraph_index"))
    char_start = _optional_int(raw.get("char_start", raw.get("char_offset")))
    char_end = _optional_int(raw.get("char_end"))
    if char_end is None and char_start is not None and quote:
        char_end = char_start + len(quote)
    return {
        "dimension": dimension,
        "issue_type": issue_type[:80],
        "severity": severity,
        "penalty": max(0, min(30, int(penalty))),
        "status": str(raw.get("status") or "open"),
        "title": title,
        "explanation": explanation,
        "quote": quote,
        "action": action,
        "replacement_text": replacement,
        "paragraph_id": raw.get("paragraph_id"),
        "paragraph_index": paragraph_index,
        "char_start": char_start,
        "char_end": char_end,
        "anchor_hash": raw.get("anchor_hash"),
        "issue_fingerprint": raw.get("issue_fingerprint"),
        "quality_evidence": raw.get("quality_evidence") if isinstance(raw.get("quality_evidence"), dict) else None,
        "detector": str(raw.get("detector") or detector),
        "confidence": _confidence(raw.get("confidence"), 0.7),
    }


def attach_paragraph_indices(md: str, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """兼容旧调用：基于 quote 粗定位并补充新维度字段。"""
    from app.services.review_anchor import locate_issue_anchor

    out: list[dict[str, Any]] = []
    for item in issues:
        issue = standardize_issue(item)
        if issue.get("quote"):
            anchor = locate_issue_anchor(
                md,
                quote=issue["quote"],
                paragraph_index=issue.get("paragraph_index"),
                paragraph_id=issue.get("paragraph_id"),
                char_start=issue.get("char_start"),
                char_end=issue.get("char_end"),
            )
            issue.update(
                {
                    "paragraph_id": anchor.paragraph_id,
                    "paragraph_index": anchor.paragraph_index,
                    "char_start": anchor.char_start,
                    "char_end": anchor.char_end,
                    "anchor_hash": anchor.anchor_hash,
                    "confidence": max(float(issue.get("confidence") or 0), anchor.confidence),
                }
            )
        issue["category"] = _legacy_category(issue["dimension"])
        issue["detail"] = issue["explanation"]
        issue["suggestion"] = issue["replacement_text"]
        issue["action_type"] = issue["action"]
        issue["char_offset"] = issue.get("char_start")
        out.append(issue)
    return out


def aggregate_review(
    detector_dimensions: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, str]:
    standardized = [standardize_issue(i, detector=str(i.get("detector") or "review_agent")) for i in issues]
    rows: list[dict[str, Any]] = []
    any_failed = False
    any_partial = False
    for key, meta in REVIEW_DIMENSIONS.items():
        det = detector_dimensions.get(key) or {}
        status = str(det.get("status") or "completed")
        if status in {"failed", "unavailable"}:
            any_failed = True
        if status == "partial":
            any_partial = True
        raw_score = clamp_score(det.get("raw_score", 70 if status not in {"failed", "unavailable"} else 0))
        active = [
            i
            for i in standardized
            if i["dimension"] == key and i.get("status", "open") not in NON_PENALTY_STATUSES
        ]
        penalty = sum(int(i.get("penalty") or 0) for i in active if i.get("status") == "open")
        effective_score = raw_score if status in {"failed", "unavailable"} else max(0, raw_score - penalty)
        rows.append(
            {
                "key": key,
                "dimension": key,
                "label": meta["label"],
                "weight": meta["weight"],
                "raw_score": raw_score,
                "effective_score": effective_score,
                "issue_count": len(active),
                "summary": str(det.get("summary") or "")[:500],
                "detector": str(det.get("detector") or meta["detector"]),
                "confidence": _confidence(det.get("confidence"), 0.7),
                "status": status,
            }
        )
    status = "failed" if any_failed and all(r["status"] in {"failed", "unavailable"} for r in rows) else "partial" if any_failed or any_partial else "completed"
    return rows, compute_total_score(rows), status


def compute_total_score(rows: list[dict[str, Any]]) -> int:
    available = [r for r in rows if str(r.get("status") or "completed") in AVAILABLE_DIMENSION_STATUSES]
    if not available:
        return 0
    numerator = sum(float(r.get("effective_score") or 0) * float(r.get("weight") or 0) for r in available)
    denom = sum(float(r.get("weight") or 0) for r in available)
    if denom <= 0:
        return 0
    return int(round(numerator / denom))


def issue_fingerprint(issue: dict[str, Any]) -> str:
    body = "|".join(
        [
            str(issue.get("dimension") or ""),
            str(issue.get("issue_type") or ""),
            str(issue.get("quote") or "")[:160],
            str(issue.get("paragraph_id") or issue.get("paragraph_index") or ""),
        ]
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]


def weights_snapshot() -> dict[str, int]:
    return {key: int(meta["weight"]) for key, meta in REVIEW_DIMENSIONS.items()}


def dimension_labels() -> dict[str, str]:
    return {key: str(meta["label"]) for key, meta in REVIEW_DIMENSIONS.items()}


def _enum(raw: str, allowed: tuple[str, ...], default: str) -> str:
    return raw if raw in allowed else default


def _optional_int(raw: Any) -> int | None:
    try:
        if raw is None or raw == "":
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def _confidence(raw: Any, default: float) -> float:
    try:
        val = float(raw)
    except (TypeError, ValueError):
        val = default
    return max(0.0, min(1.0, round(val, 3)))


def _legacy_category(dimension: str) -> str:
    return {
        "logic_structure": "logic",
        "language_grammar": "grammar",
        "style_consistency": "style",
        "citation_sources": "citation",
        "factual_support": "hallucination",
        "figure_quality": "figure",
        "ai_signature": "other",
    }.get(dimension, "other")
