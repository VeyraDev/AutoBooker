"""上传资料语义解析与冲突检测。"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.llm.client import LLMClient
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(
    r"^(第[一二三四五六七八九十百千\d]+[章节篇部]|Chapter\s+\d+|[\d]+[\.\)、]\s*|\#{1,3}\s+)(.+)$",
    re.IGNORECASE,
)


def _extract_outline_candidate(text: str) -> list[dict[str, Any]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    chapters: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for ln in lines[:400]:
        m = _HEADING_RE.match(ln)
        if m and len(m.group(2)) < 120:
            if current:
                chapters.append(current)
            current = {"title": m.group(2).strip(), "sections": [], "key_points": []}
        elif current and len(ln) < 200 and not m:
            if ln.startswith(("-", "•", "*", "·")) or re.match(r"^\d+[\.\)、]", ln):
                current.setdefault("key_points", []).append(ln.lstrip("-•*· ").strip())
    if current:
        chapters.append(current)
    for i, ch in enumerate(chapters, start=1):
        ch["index"] = i
    return chapters[:40]


def parse_file_artifacts(
    text: str,
    filename: str,
    file_purposes: list[str],
    user_note: str = "",
    *,
    model: str | None = None,
) -> dict[str, Any]:
    """返回 parse_artifacts JSON 结构。"""
    purposes = file_purposes or ["reference"]
    excerpt = text[:12000]
    outline_candidate = _extract_outline_candidate(text) if "outline" in purposes else []
    writing_rules: list[str] = []
    terminology: list[dict[str, str]] = []

    if "writing_requirements" in purposes:
        try:
            client = LLMClient()
            prompt = f"""从以下文档摘录全书级写作要求（文风、术语、禁止事项等），输出 JSON：
{{"writing_rules":["..."], "terminology":[{{"term":"...", "definition":"..."}}]}}
文件名：{filename}
用户备注：{user_note or "无"}

文档摘录：
{excerpt[:6000]}"""
            out = client.chat_completion(
                [
                    {"role": "system", "content": "只输出 JSON"},
                    {"role": "user", "content": prompt},
                ],
                model=model,
                max_tokens=1500,
                temperature=0.2,
            )
            data = parse_llm_json(out)
            if isinstance(data.get("writing_rules"), list):
                writing_rules = [str(x)[:500] for x in data["writing_rules"]][:30]
            if isinstance(data.get("terminology"), list):
                terminology = [
                    {"term": str(t.get("term", ""))[:80], "definition": str(t.get("definition", ""))[:300]}
                    for t in data["terminology"]
                    if isinstance(t, dict) and t.get("term")
                ][:40]
        except Exception as exc:
            logger.warning("writing rules extract failed: %s", exc)
            if user_note:
                writing_rules = [user_note[:2000]]

    return {
        "status": "candidate",
        "filename": filename,
        "purposes": purposes,
        "user_note": user_note or None,
        "outline_candidate": outline_candidate,
        "writing_rules": writing_rules,
        "terminology": terminology,
        "paragraph_count": len([ln for ln in text.splitlines() if ln.strip()]),
    }


def detect_primary_outline_conflicts(db, book_id) -> list[dict[str, Any]]:
    from app.models.reference import OutlineUsage, ReferenceFile

    primaries = (
        db.query(ReferenceFile)
        .filter(
            ReferenceFile.book_id == book_id,
            ReferenceFile.outline_usage == OutlineUsage.primary,
        )
        .all()
    )
    if len(primaries) <= 1:
        return []
    return [
        {
            "type": "multiple_primary_outlines",
            "status": "pending",
            "message": "存在多份「主大纲」文件，请选择采用哪一份。",
            "file_ids": [str(f.id) for f in primaries],
            "options": [{"id": str(f.id), "label": f.filename} for f in primaries],
        }
    ]


def get_primary_outline_for_book(db, book_id) -> list[dict[str, Any]] | None:
    from app.models.reference import OutlineUsage, ReferenceFile

    ref = (
        db.query(ReferenceFile)
        .filter(
            ReferenceFile.book_id == book_id,
            ReferenceFile.outline_usage == OutlineUsage.primary,
        )
        .order_by(ReferenceFile.created_at.desc())
        .first()
    )
    if not ref or not isinstance(ref.parse_artifacts, dict):
        return None
    cand = ref.parse_artifacts.get("outline_candidate")
    return cand if isinstance(cand, list) and cand else None


def get_book_level_writing_rules(db, book_id) -> list[str]:
    from app.models.reference import ReferenceFile

    rules: list[str] = []
    rows = db.query(ReferenceFile).filter(ReferenceFile.book_id == book_id).all()
    for ref in rows:
        art = ref.parse_artifacts if isinstance(ref.parse_artifacts, dict) else {}
        if art.get("status") == "disabled":
            continue
        for r in art.get("writing_rules") or []:
            s = str(r).strip()
            if s and s not in rules:
                rules.append(s)
    return rules[:40]

