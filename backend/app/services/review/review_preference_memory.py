"""Persist lightweight user review preferences into project memory."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.services.assistant.project_memory_service import ProjectMemoryService


_DIMENSION_LABELS = {
    "argument_quality": "论证质量",
    "structure_progress": "结构推进",
    "language_credibility": "语言可信度",
    "publication_delivery": "出版交付",
    "reference": "引用来源",
    "ai_text_risk": "AI 文本风险",
    "goal_alignment": "目标一致性",
    "content": "内容审校",
    "copyediting": "编校语言",
    "layout": "排版图表",
}


def _clean(value: object, *, default: str = "未分类") -> str:
    text = str(value or "").strip()
    return text[:80] if text else default


def _label_dimension(value: object) -> str:
    key = _clean(value, default="content")
    return _DIMENSION_LABELS.get(key, key)


def _content_for_preference(
    *,
    decision: str,
    product_dimension: object,
    issue_type: object,
    fix_capability: object = None,
) -> str | None:
    dimension = _label_dimension(product_dimension)
    issue = _clean(issue_type)
    fix = _clean(fix_capability, default="")
    subject = f"{dimension} / {issue}"
    if decision == "dismissed":
        return (
            f"审校偏好：用户曾忽略或拒绝「{subject}」类审校建议；后续同类建议如果缺少强依据、"
            "只属于风格偏好或无法准确定位，应降级为观察项，并明确说明是否必要修改。"
        )
    if decision == "accepted":
        suffix = "，但仍需保留原文定位和依据"
        if fix == "preview_apply":
            suffix = "；后续同类低风险问题可优先提供预览后一键应用，但仍需保留原文定位和依据"
        return f"审校偏好：用户曾接受「{subject}」类审校建议{suffix}。"
    return None


def record_review_preference(
    db: Session,
    book_id: UUID,
    *,
    decision: str,
    product_dimension: object,
    issue_type: object,
    fix_capability: object = None,
) -> None:
    """Record a confirmed, low-weight preference from user review actions.

    This deliberately stores coarse category preferences rather than exact finding
    text, so one action nudges future review behavior without becoming a hard rule.
    """
    content = _content_for_preference(
        decision=decision,
        product_dimension=product_dimension,
        issue_type=issue_type,
        fix_capability=fix_capability,
    )
    if not content:
        return
    ProjectMemoryService(db).upsert_from_update(
        book_id,
        content=content,
        memory_type="decision",
        strength="preference",
        confirmed=True,
    )
