"""Suggestion-only book settings inference for startup assistant / quick_fill."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.models.book import Book, BookType, CitationStyle
from app.services.assistant.book_settings_context import current_book_settings, get_setting_origins, protected_origins
from app.services.assistant.source_retrieve_service import retrieve_source_context
from app.services.writing.project_seed import (
    _normalize_discipline_candidates,
    _normalize_disciplines,
    _pair_type_and_style,
    is_provisional_classification,
    resolve_project_seed,
)
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_SUGGEST_FIELDS = (
    "book_type",
    "style_type",
    "target_audience",
    "disciplines",
    "topic_brief",
    "target_words",
    "topic_tags",
    "citation_style",
)


def suggest_book_settings(
    db: Session | None,
    book: Book,
    *,
    model: str,
    fields_to_complete: list[str] | None = None,
    relevant_source_ids: list[str] | None = None,
    mode: str = "quick_fill",
) -> dict[str, Any]:
    """Infer settings suggestions without writing the database.

    Does not invent defaults for unresolved fields; leaves them out of suggestions.
    """
    seed = resolve_project_seed(book, db)
    current = current_book_settings(book)
    origins = get_setting_origins(book)
    protected = protected_origins()

    wanted = [f for f in (fields_to_complete or list(_SUGGEST_FIELDS)) if f in _SUGGEST_FIELDS]
    # Skip fields already protected unless empty
    effective: list[str] = []
    for field in wanted:
        meta = origins.get(field) if isinstance(origins.get(field), dict) else {}
        origin = str(meta.get("origin") or "")
        cur = current.get(field)
        empty = cur is None or cur == "" or cur == [] or cur == 0
        if origin in protected and not empty:
            continue
        effective.append(field)

    evidence_bits: list[str] = []
    if seed:
        evidence_bits.append(f"项目种子：{seed[:1200]}")
    if db is not None:
        try:
            retrieved = retrieve_source_context(
                db,
                book,
                query="书稿主题 类型 读者 学科 篇幅 引用 大纲 写作要求",
                source_ids=relevant_source_ids,
                top_k=10,
            )
            for seg in retrieved.get("segments") or []:
                evidence_bits.append(
                    f"资料[{seg.get('location') or seg.get('source_id')}]：{(seg.get('text') or '')[:400]}"
                )
        except Exception as exc:
            logger.warning("suggest_book_settings retrieve failed: %s", exc)

    evidence_block = "\n".join(evidence_bits)[:6000] or "（暂无额外资料）"
    current_bt = book.book_type.value if book.book_type else "nonfiction"
    current_st = book.style_type or ""

    prompt = f"""根据证据推断书稿设定建议。只输出 JSON，不要编造无依据字段：
{{
  "suggestions": {{
    "book_type": "nonfiction|academic|null",
    "style_type": "popular_science|practical_guide|reference_tool|insight_opinion|textbook|technical_deep_dive|ai_review_commentary|null",
    "target_audience": "具体读者或 null",
    "disciplines": ["..."] 或 [],
    "topic_brief": "..." 或 null,
    "target_words": 80000 或 null,
    "topic_tags": ["..."] 或 [],
    "citation_style": "apa|gb_t7714|none|null"
  }},
  "decisions": [
    {{"field": "style_type", "reason": "...", "evidence": ["..."], "confidence": 0.0}}
  ],
  "unresolved_fields": ["无法可靠判断的字段名"]
}}

约束：
- mode={mode}；仅对需要补齐的字段给出建议：{effective}
- 证据不足时该字段放 unresolved_fields，suggestions 里用 null / []，禁止用泛化读者、默认字数、默认 APA 凑数
- 当前占位分类 {current_bt}/{current_st} 不是结论；按证据重判
- 不要覆盖已有明确设定：{ {k: current.get(k) for k in effective} }

证据：
{evidence_block}
"""
    data: dict[str, Any] = {}
    try:
        out = LLMClient().chat_completion(
            [
                {
                    "role": "system",
                    "content": "只输出 JSON。无充分依据不要填满设定，不要使用泛化默认值。",
                },
                {"role": "user", "content": prompt},
            ],
            model=model,
            max_tokens=1400,
            temperature=0.2,
            disable_thinking=True,
        )
        data = parse_llm_json(out)
    except Exception:
        logger.exception("suggest_book_settings LLM failed book=%s", book.id)
        data = {}

    raw_sugg = data.get("suggestions") if isinstance(data.get("suggestions"), dict) else {}
    decisions_in = data.get("decisions") if isinstance(data.get("decisions"), list) else []
    unresolved = [
        str(x) for x in (data.get("unresolved_fields") or []) if str(x).strip()
    ]

    suggestions: dict[str, Any] = {}
    decisions: list[dict[str, Any]] = []

    # Type / style pairing when present
    if "book_type" in effective or "style_type" in effective:
        bt_raw = str(raw_sugg.get("book_type") or "").strip()
        st_raw = str(raw_sugg.get("style_type") or "").strip()
        if bt_raw or st_raw:
            fallback_type = book.book_type or BookType.nonfiction
            fallback_style = (book.style_type or "").strip()
            if is_provisional_classification(book) and not bt_raw and not st_raw:
                fallback_type = BookType.nonfiction
                fallback_style = ""
            paired_type, paired_style = _pair_type_and_style(
                bt_raw,
                st_raw,
                fallback_type=fallback_type,
                fallback_style=fallback_style,
            )
            if "book_type" in effective and bt_raw:
                suggestions["book_type"] = paired_type.value
            if "style_type" in effective and (st_raw or bt_raw):
                suggestions["style_type"] = paired_style

    if "target_audience" in effective:
        aud = str(raw_sugg.get("target_audience") or "").strip()
        if aud and aud not in {"大众读者", "对相关主题感兴趣的读者", "一般读者"}:
            suggestions["target_audience"] = aud[:500]
        elif "target_audience" not in unresolved:
            unresolved.append("target_audience")

    if "disciplines" in effective:
        disciplines = _normalize_disciplines(raw_sugg.get("disciplines"))
        if disciplines:
            suggestions["disciplines"] = disciplines
        elif "disciplines" not in unresolved:
            unresolved.append("disciplines")

    if "topic_brief" in effective:
        brief = str(raw_sugg.get("topic_brief") or "").strip()
        if brief:
            suggestions["topic_brief"] = brief[:3000]
        elif "topic_brief" not in unresolved:
            unresolved.append("topic_brief")

    if "target_words" in effective:
        try:
            words = int(raw_sugg.get("target_words") or 0)
        except (TypeError, ValueError):
            words = 0
        if 10_000 <= words <= 500_000:
            suggestions["target_words"] = words
        elif "target_words" not in unresolved:
            unresolved.append("target_words")

    if "topic_tags" in effective:
        tags = raw_sugg.get("topic_tags") or []
        if isinstance(tags, list) and tags:
            suggestions["topic_tags"] = [str(t)[:50] for t in tags if str(t).strip()][:8]
        elif "topic_tags" not in unresolved:
            unresolved.append("topic_tags")

    if "citation_style" in effective:
        cs = str(raw_sugg.get("citation_style") or "").strip().lower()
        if cs in {"apa", "gb_t7714", "none"}:
            suggestions["citation_style"] = cs
        elif "citation_style" not in unresolved:
            unresolved.append("citation_style")

    for d in decisions_in:
        if not isinstance(d, dict) or not d.get("field"):
            continue
        field = str(d.get("field"))
        if field not in suggestions and field not in unresolved:
            continue
        decisions.append(
            {
                "field": field,
                "reason": str(d.get("reason") or "").strip()[:400],
                "evidence": [str(x)[:200] for x in (d.get("evidence") or []) if str(x).strip()][:6],
                "confidence": float(d.get("confidence") or 0) if d.get("confidence") is not None else None,
                "decision_type": "suggested",
            }
        )

    # Ensure a decision stub for each suggestion
    have = {d["field"] for d in decisions}
    for field in suggestions:
        if field not in have:
            decisions.append(
                {
                    "field": field,
                    "reason": "基于项目种子与已读资料的推断",
                    "evidence": ["项目种子", "资料片段"],
                    "confidence": 0.7,
                    "decision_type": "suggested",
                }
            )

    # Drop unresolved that we actually resolved
    unresolved = [f for f in unresolved if f not in suggestions]
    candidates = _normalize_discipline_candidates([], suggestions.get("disciplines") or [])

    return {
        "suggestions": suggestions,
        "decisions": decisions,
        "unresolved_fields": unresolved,
        "discipline_candidates": candidates,
        "mode": mode,
        "protected_skipped": [
            f
            for f in wanted
            if f not in effective
        ],
    }


def apply_book_settings_suggestion(
    book: Book,
    suggestion: dict[str, Any],
    *,
    fill_defaults: bool = False,
) -> dict[str, Any]:
    """Apply a suggestion dict to Book. Used by legacy one-click paths when fill_defaults=True."""
    from app.services.writing.project_seed import mark_classification_source

    sugg = suggestion.get("suggestions") if isinstance(suggestion.get("suggestions"), dict) else suggestion
    applied: dict[str, Any] = {}

    bt = sugg.get("book_type")
    st = sugg.get("style_type")
    if bt or st:
        paired_type, paired_style = _pair_type_and_style(
            str(bt or (book.book_type.value if book.book_type else "")),
            str(st or (book.style_type or "")),
            fallback_type=book.book_type or BookType.nonfiction,
            fallback_style=(book.style_type or "popular_science"),
        )
        book.book_type = paired_type
        book.style_type = paired_style
        mark_classification_source(book, "inferred")
        applied["book_type"] = paired_type.value
        applied["style_type"] = paired_style

    if sugg.get("target_words") is not None:
        try:
            words = int(sugg["target_words"])
        except (TypeError, ValueError):
            words = 0
        if 10_000 <= words <= 500_000:
            book.target_words = words
            applied["target_words"] = words
    elif fill_defaults and not book.target_words:
        from app.services.writing.project_seed import _DEFAULT_WORDS

        book.target_words = _DEFAULT_WORDS.get(book.book_type or BookType.nonfiction, 80_000)
        applied["target_words"] = book.target_words

    if sugg.get("target_audience"):
        book.target_audience = str(sugg["target_audience"])[:500]
        applied["target_audience"] = book.target_audience
    elif fill_defaults and not (book.target_audience or "").strip():
        book.target_audience = "对相关主题感兴趣的读者"
        applied["target_audience"] = book.target_audience

    disciplines = _normalize_disciplines(sugg.get("disciplines"))
    if disciplines:
        book.disciplines = disciplines
        book.discipline = disciplines[0]
        applied["disciplines"] = disciplines

    if sugg.get("topic_tags") and not book.topic_tags:
        tags = sugg["topic_tags"]
        book.topic_tags = [str(t)[:50] for t in tags][:8] if isinstance(tags, list) else []
        applied["topic_tags"] = list(book.topic_tags or [])

    if sugg.get("citation_style") is not None:
        cs = str(sugg.get("citation_style") or "").lower()
        if cs in ("none", "无", "无需"):
            book.citation_style = None
            applied["citation_style"] = "none"
        elif cs == "gb_t7714":
            book.citation_style = CitationStyle.gb_t7714
            applied["citation_style"] = "gb_t7714"
        elif cs == "apa":
            book.citation_style = CitationStyle.apa
            applied["citation_style"] = "apa"
    elif fill_defaults and not book.citation_style:
        book.citation_style = CitationStyle.apa
        applied["citation_style"] = "apa"

    brief = str(sugg.get("topic_brief") or "").strip()
    if brief and not (book.topic_brief or "").strip():
        book.topic_brief = brief[:3000]
        applied["topic_brief"] = book.topic_brief

    return applied
