"""Task-routed chapter review with separate detection responsibilities."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.llm.client import LLMClient
from app.prompts.review_quality import ReviewTask, build_review_prompt
from app.services.review.review_finding_validator import classify_product_dimension, route_finding_fix
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

MAX_ISSUES = 18
MAX_LONG_CHAPTER_ISSUES = 30

# Compatibility export only. Runtime calls build_review_prompt(task, profile).
REVIEW_SYSTEM = build_review_prompt("content_argument", "default")

_TASK_DIMENSIONS: dict[ReviewTask, tuple[str, ...]] = {
    "content_argument": ("logic_structure", "style_consistency"),
    "reference_evidence": ("factual_support", "citation_sources"),
    "language_ai": ("language_grammar", "style_consistency", "ai_signature"),
}

_FACT_SIGNAL_RE = re.compile(
    r"(?:\d+(?:\.\d+)?\s*(?:%|％|亿元|万元|万人|人|家|项|年|月|日)|"
    r"(?:19|20)\d{2}年|研究(?:表明|发现|显示)|数据(?:表明|显示)|据(?:报道|统计|调查)|"
    r"报告(?:指出|显示)|调查(?:表明|显示)|政策|条例|办法|任职|担任|创立|成立|增长|下降|占比)"
)
_CITATION_SIGNAL_RE = re.compile(r"\[[0-9]{1,3}\]|\([^()]{1,40},\s*(?:19|20)\d{2}\)|《[^》]{2,80}》")


class ReviewAgent:
    """Run three focused reviewers, then merge and route findings in code."""

    def __init__(self, *, model: str) -> None:
        self._model = model
        self._client = LLMClient()

    def review_chapter(
        self,
        *,
        chapter_title: str,
        body: str,
        book_title: str,
        book_type: str,
        citation_style: str,
        review_profile: str = "",
        review_instruction: str = "",
        user_material: str = "",
        narrative_constitution: str = "",
        approved_citations: list[str] | None = None,
        figure_summaries: list[str] | None = None,
    ) -> dict[str, Any]:
        text = (body or "").strip()
        if not text:
            return {"summary": "本章暂无正文，无法审校。", "dimensions": {}, "issues": []}

        profile = review_profile or book_type
        common = {
            "chapter_title": chapter_title,
            "book_title": book_title,
            "book_type": book_type,
            "citation_style": citation_style,
            "review_instruction": review_instruction,
        }
        task_results: list[tuple[ReviewTask, list[dict[str, Any]], bool]] = []

        content_input = _content_argument_input(
            common,
            text,
            user_material=user_material,
            narrative_constitution=narrative_constitution,
            figure_summaries=figure_summaries or [],
        )
        content_issues, content_ok = self._run_task(
            "content_argument",
            profile=profile,
            user_content=content_input,
        )
        task_results.append(("content_argument", content_issues, content_ok))

        claims = _extract_fact_claims(text)
        citation_rows = list(approved_citations or [])[:60]
        if claims or citation_rows:
            reference_issues: list[dict[str, Any]] = []
            reference_ok = True
            for claim_batch in _batch_items(claims, 30) or [[]]:
                reference_input = _reference_evidence_input(
                    common,
                    claim_batch,
                    approved_citations=citation_rows,
                    user_material=user_material,
                )
                batch_issues, batch_ok = self._run_task(
                    "reference_evidence",
                    profile=profile,
                    user_content=reference_input,
                )
                reference_issues.extend(batch_issues)
                reference_ok = reference_ok and batch_ok
            task_results.append(("reference_evidence", reference_issues, reference_ok))

        language_issues: list[dict[str, Any]] = []
        language_ok = True
        language_chunks = _split_language_chunks(text)
        for index, chunk in enumerate(language_chunks, start=1):
            language_input = _language_ai_input(
                common,
                chunk,
                chunk_index=index,
                chunk_count=len(language_chunks),
                user_material=user_material,
            )
            chunk_issues, chunk_ok = self._run_task(
                "language_ai",
                profile=profile,
                user_content=language_input,
            )
            language_issues.extend(chunk_issues)
            language_ok = language_ok and chunk_ok
        task_results.append(("language_ai", language_issues, language_ok))

        issues = _merge_task_findings(task_results)
        issue_limit = MAX_LONG_CHAPTER_ISSUES if len(text) > 18_000 else MAX_ISSUES
        issues = issues[:issue_limit]
        dimensions = _dimensions_from_findings(task_results)
        completed = sum(1 for _, _, ok in task_results if ok)
        total = len(task_results)
        if issues:
            summary = f"已完成 {completed}/{total} 类专项审校，保留 {len(issues)} 条待验证问题。"
        elif completed == total:
            summary = "专项审校已完成，未发现有充分依据且值得立即处理的问题。"
        else:
            summary = f"已完成 {completed}/{total} 类专项审校；部分审校器暂未返回可解析结果。"
        return {"summary": summary, "dimensions": dimensions, "issues": issues}

    def _run_task(
        self,
        task: ReviewTask,
        *,
        profile: str,
        user_content: str,
    ) -> tuple[list[dict[str, Any]], bool]:
        try:
            raw = self._client.chat_completion(
                [
                    {"role": "system", "content": build_review_prompt(task, profile)},
                    {"role": "user", "content": user_content},
                ],
                model=self._model,
                max_tokens=4096,
                temperature=0.25,
            )
        except Exception as exc:
            logger.warning("review task call failed task=%s: %s", task, exc)
            return [], False
        try:
            data = parse_llm_json(raw)
        except Exception as exc:
            logger.warning("review task JSON parse failed task=%s: %s", task, exc)
            return [], False
        raw_findings = data.get("findings") or data.get("issues") or []
        if not isinstance(raw_findings, list):
            return [], False
        normalized = [
            item
            for index, raw_item in enumerate(raw_findings[:16])
            if isinstance(raw_item, dict)
            for item in [_normalize_detection_finding(raw_item, task=task, index=index)]
        ]
        return normalized, True


def _normalize_detection_finding(
    item: dict[str, Any],
    *,
    task: ReviewTask,
    index: int,
) -> dict[str, Any]:
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    quote = str(item.get("quote") or location.get("quote") or "")[:800]
    severity = _enum_val(
        item.get("proposed_severity") or item.get("severity"),
        ("high", "medium", "low", "needs_verification"),
        "medium",
    )
    evidence = _as_str_list(item.get("evidence"))
    basis_refs = _as_str_list(item.get("basis_refs"))
    basis_rule_ids = _as_str_list(item.get("basis_rule_ids"))
    raw_finding: dict[str, Any] = {
        "id": str(item.get("id") or f"{task}_{index + 1}"),
        "dimension": str(item.get("dimension") or _TASK_DIMENSIONS[task][0]),
        "issue_type": str(item.get("issue_type") or f"{task}_issue")[:80],
        "severity": severity,
        "penalty": _penalty(None, severity),
        "category": _enum_val(
            item.get("category"),
            ("logic", "style", "grammar", "citation", "structure", "hallucination", "figure", "code", "consistency", "other"),
            "other",
        ),
        "title": str(item.get("title") or "待核对问题")[:80],
        "detail": "；".join(evidence)[:2000] or str(item.get("detail") or "")[:2000],
        "why_it_matters": str(item.get("why_it_matters") or "")[:2000],
        "quote": quote,
        "suggestion": "",
        "replacement_text": "",
        "paragraph_index": _optional_int(item.get("paragraph_index") or location.get("paragraph_index")),
        "char_start": _optional_int(item.get("char_start") or location.get("char_start")),
        "char_end": _optional_int(item.get("char_end") or location.get("char_end")),
        "confidence": _confidence(item.get("confidence")),
        "basis_refs": basis_refs,
        "basis_rule_ids": basis_rule_ids,
        "evidence": evidence,
        "verification_status": str(item.get("verification_status") or ""),
        "detector": f"review_agent:{task}",
        "review_task": task,
    }
    routed = route_finding_fix(raw_finding)
    raw_finding.update(routed)
    raw_finding["product_dimension"] = classify_product_dimension(raw_finding)
    raw_finding["quality_evidence"] = _quality_evidence(raw_finding, location=location)
    return raw_finding


def _content_argument_input(
    common: dict[str, str],
    text: str,
    *,
    user_material: str,
    narrative_constitution: str,
    figure_summaries: list[str],
) -> str:
    parts = [
        _render_book_context(common),
        "【章节结构材料】\n" + _build_structure_digest(text),
    ]
    if narrative_constitution.strip():
        parts.append("【与结构有关的叙事约束】\n" + narrative_constitution.strip()[:2600])
    if user_material.strip():
        excerpt = _select_context_blocks(
            user_material,
            allowed_titles=("写作依据", "已确认理解", "写作方案", "输入意图", "必须保留", "必须避免", "项目长期记忆", "大纲规则", "已确认写作要求", "写作要求", "术语"),
            budget=5000,
        )
        if excerpt:
            parts.append("【用户确认的写作要求】\n" + excerpt)
    if figure_summaries:
        parts.append("【本章图表语义摘要】\n" + "\n".join(figure_summaries[:20]))
    return "\n\n".join(parts)


def _reference_evidence_input(
    common: dict[str, str],
    claims: list[dict[str, Any]],
    *,
    approved_citations: list[str],
    user_material: str,
) -> str:
    parts = [
        _render_book_context(common),
        "【待核验事实主张】\n" + json.dumps(claims, ensure_ascii=False),
    ]
    if approved_citations:
        parts.append("【本章命中的已绑定文献】\n" + "\n".join(approved_citations[:60]))
    if user_material.strip():
        excerpt = _select_context_blocks(
            user_material,
            allowed_titles=("资料使用规则", "引用要求", "资料使用策略", "本书文献与核验状态", "本阶段检索到的资料依据", "用户资料（兼容）"),
            budget=9000,
        )
        if excerpt:
            parts.append("【本章命中的资料依据】\n" + excerpt)
    return "\n\n".join(parts)


def _language_ai_input(
    common: dict[str, str],
    chunk: str,
    *,
    chunk_index: int,
    chunk_count: int,
    user_material: str,
) -> str:
    parts = [
        _render_book_context(common),
        f"【局部正文 {chunk_index}/{chunk_count}】\n{_preprocess_code_blocks(chunk)}",
    ]
    if user_material.strip():
        excerpt = _select_context_blocks(
            user_material,
            allowed_titles=("必须保留", "必须避免", "已确认写作要求", "写作要求", "术语"),
            budget=3000,
        )
        if excerpt:
            parts.append("【术语、禁忌与明确写作要求】\n" + excerpt)
    return "\n\n".join(parts)


def _render_book_context(common: dict[str, str]) -> str:
    lines = [
        f"书名：{common.get('book_title') or '未命名'}",
        f"书类：{common.get('book_type') or '未指定'}",
        f"章节标题：{common.get('chapter_title') or '未命名章节'}",
        f"引用格式：{common.get('citation_style') or '未指定'}",
    ]
    instruction = str(common.get("review_instruction") or "").strip()
    if instruction:
        lines.append(f"专项审校要求：{instruction[:1200]}")
    return "\n".join(lines)


def _select_context_blocks(
    text: str,
    *,
    allowed_titles: tuple[str, ...],
    budget: int,
) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    blocks = re.findall(r"【([^】]+)】\s*([\s\S]*?)(?=\n【[^】]+】|\Z)", raw)
    if not blocks:
        return raw[:budget]
    selected: list[str] = []
    used = 0
    for title, content in blocks:
        if not any(allowed in title for allowed in allowed_titles):
            continue
        piece = f"【{title}】\n{content.strip()}"
        if used + len(piece) > budget:
            remaining = budget - used
            if remaining > len(title) + 4:
                selected.append(piece[:remaining])
            break
        selected.append(piece)
        used += len(piece)
    return "\n\n".join(selected)


def _build_structure_digest(text: str, *, limit: int = 14_000) -> str:
    if len(text) <= limit:
        return text
    sections: list[tuple[str, list[str]]] = []
    title = "章首"
    body: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        stripped = paragraph.strip()
        if not stripped:
            continue
        if re.match(r"^#{1,6}\s+", stripped):
            if body:
                sections.append((title, body))
            title = stripped[:160]
            body = []
        else:
            body.append(stripped)
    if body:
        sections.append((title, body))
    lines = ["以下为长章结构摘要，只用于全章关系判断："]
    for heading, paragraphs in sections:
        lines.append(heading)
        selected = paragraphs[:2] + (paragraphs[-2:] if len(paragraphs) > 2 else [])
        for paragraph in selected:
            lines.append(paragraph[:900])
        if sum(len(line) for line in lines) >= limit:
            break
    return "\n\n".join(lines)[:limit]


def _extract_fact_claims(text: str, *, limit: int = 120) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    offset = 0
    paragraph_index = 0
    for match in re.finditer(r"[^\n]+(?:\n|$)", text):
        raw = match.group(0)
        paragraph = raw.strip()
        if not paragraph:
            continue
        if paragraph.startswith(("#", "```", "|")):
            offset = match.end()
            continue
        if _FACT_SIGNAL_RE.search(paragraph) or _CITATION_SIGNAL_RE.search(paragraph):
            claims.append(
                {
                    "claim_id": f"c{len(claims) + 1}",
                    "quote": paragraph[:900],
                    "paragraph_index": paragraph_index,
                    "char_start": match.start(),
                    "char_end": min(match.start() + len(paragraph), match.end()),
                }
            )
            if len(claims) >= limit:
                break
        paragraph_index += 1
        offset = match.end()
    return claims


def _batch_items(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _split_language_chunks(text: str, *, limit: int = 7000) -> list[str]:
    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= limit:
            units.append(paragraph)
            continue
        sentences = [part.strip() for part in re.split(r"(?<=[。！？；!?;])", paragraph) if part.strip()]
        buffer = ""
        for sentence in sentences or [paragraph]:
            if buffer and len(buffer) + len(sentence) > limit:
                units.append(buffer)
                buffer = sentence
            else:
                buffer += sentence
        if buffer:
            units.append(buffer)

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    previous_tail = ""
    for unit in units:
        extra = len(unit) + (2 if current else 0)
        if current and current_len + extra > limit:
            chunks.append("\n\n".join(current))
            previous_tail = current[-1]
            current = [previous_tail, unit] if len(previous_tail) + len(unit) + 2 <= limit else [unit]
            current_len = sum(len(item) for item in current) + max(0, len(current) - 1) * 2
        else:
            current.append(unit)
            current_len += extra
    if current:
        chunks.append("\n\n".join(current))
    return chunks or [text]


def _merge_task_findings(
    task_results: list[tuple[ReviewTask, list[dict[str, Any]], bool]],
) -> list[dict[str, Any]]:
    severity_rank = {"high": 0, "needs_verification": 1, "medium": 2, "low": 3}
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for _, findings, _ in task_results:
        for item in findings:
            key = (
                str(item.get("issue_type") or ""),
                _normalize_quote(str(item.get("quote") or item.get("title") or ""))[:180],
            )
            current = selected.get(key)
            if current is None or _confidence(item.get("confidence")) > _confidence(current.get("confidence")):
                selected[key] = item
    out = list(selected.values())
    out.sort(
        key=lambda item: (
            severity_rank.get(str(item.get("severity") or "medium"), 2),
            -_confidence(item.get("confidence")),
        )
    )
    return out


def _dimensions_from_findings(
    task_results: list[tuple[ReviewTask, list[dict[str, Any]], bool]],
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for task, findings, ok in task_results:
        for dimension in _TASK_DIMENSIONS[task]:
            relevant = [item for item in findings if item.get("dimension") == dimension]
            penalty = sum(_penalty(item.get("penalty"), item.get("severity")) for item in relevant)
            rows[dimension] = {
                "raw_score": max(0, 96 - min(36, penalty)),
                "summary": f"{task} 专项发现 {len(relevant)} 条候选问题。" if ok else f"{task} 专项结果不可用。",
                "confidence": round(sum(_confidence(item.get("confidence")) for item in relevant) / max(1, len(relevant)), 3) if relevant else (0.78 if ok else 0.0),
                "detector": f"review_agent:{task}",
                "status": "completed" if ok else "partial",
            }
    return rows


def _preprocess_code_blocks(text: str) -> str:
    notes: list[str] = []
    for match in re.finditer(r"```(\w+)?\n([\s\S]*?)```", text):
        body = match.group(2) or ""
        if body.count("(") != body.count(")"):
            notes.append("某代码块圆括号可能不匹配")
        if body.count("{") != body.count("}"):
            notes.append("某代码块花括号可能不匹配")
    if notes:
        return text + "\n\n【程序预扫描提示】" + "；".join(dict.fromkeys(notes))
    return text


def _normalize_quote(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _as_str_list(raw: Any) -> list[str]:
    if raw in (None, ""):
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [str(raw).strip()]


def _quality_evidence(item: dict[str, Any], *, location: dict[str, Any]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for key in (
        "product_dimension",
        "why_it_matters",
        "fix_capability",
        "verification_status",
        "tier",
        "action_options",
        "basis_refs",
        "basis_rule_ids",
        "evidence",
        "review_task",
    ):
        value = item.get(key)
        if value not in (None, "", []):
            meta[key] = value
    clean_location = {str(key): value for key, value in location.items() if value not in (None, "", [])}
    if clean_location:
        meta["location"] = clean_location
    return meta


def _enum_val(raw: Any, allowed: tuple[str, ...], default: str) -> str:
    value = str(raw or "").strip().lower()
    return value if value in allowed else default


def _penalty(raw: Any, severity: Any) -> int:
    try:
        return max(0, min(30, int(raw)))
    except (TypeError, ValueError):
        return {"high": 10, "needs_verification": 5, "medium": 6, "low": 3}.get(str(severity or "").lower(), 6)


def _optional_int(raw: Any) -> int | None:
    try:
        if raw is None or raw == "":
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def _confidence(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.7
    return max(0.0, min(1.0, round(value, 3)))
