"""Unified project seed for settings inference, literature search, and outline topic.

Book title (often the placeholder 「书稿1」) must not drive theme inference.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.models.book import Book, BookType, CitationStyle
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_NONFICTION_STYLES = frozenset(
    {"popular_science", "practical_guide", "reference_tool", "insight_opinion"}
)
_ACADEMIC_STYLES = frozenset(
    {"textbook", "technical_deep_dive", "ai_review_commentary"}
)
_DEFAULT_WORDS = {BookType.nonfiction: 80_000, BookType.academic: 200_000}

_PLACEHOLDER_TITLES = frozenset({"书稿1", "未命名书稿", "untitled", "new book"})


def _normalize_disciplines(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()[:100]
        if text and text not in out:
            out.append(text)
        if len(out) >= 3:
            break
    return out


def _normalize_discipline_candidates(items: object, disciplines: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if isinstance(items, list):
        for item in items:
            raw = item if isinstance(item, dict) else {"name": item}
            name = str(raw.get("name") or "").strip()[:100]
            if not name or any(c["name"] == name for c in out):
                continue
            out.append(
                {
                    "name": name,
                    "reason": str(raw.get("reason") or "").strip()[:240]
                    or "该领域会影响本书术语解释、证据选择和论证边界。",
                    "ambiguity_note": str(raw.get("ambiguity_note") or "").strip()[:240],
                }
            )
            if len(out) >= 3:
                break
    for name in disciplines:
        if not any(c["name"] == name for c in out):
            out.append(
                {
                    "name": name,
                    "reason": "该领域会影响本书术语解释、证据选择和论证边界。",
                    "ambiguity_note": "",
                }
            )
            if len(out) >= 3:
                break
    return out


def resolve_project_seed(book: Book, db: Session | None = None) -> str:
    """User intent → topic_brief → (non-placeholder) title. Never prefer 「书稿1」."""
    parts: list[str] = []

    if db is not None:
        from app.models.intake import IntakeStatus, ProjectIntake

        intake = (
            db.query(ProjectIntake)
            .filter(
                ProjectIntake.book_id == book.id,
                ProjectIntake.status != IntakeStatus.superseded,
            )
            .order_by(ProjectIntake.created_at.desc())
            .first()
        )
        if intake and (intake.raw_goal_text or "").strip():
            parts.append(intake.raw_goal_text.strip()[:4000])

    brief = (book.topic_brief or "").strip()
    if brief and brief not in parts:
        parts.append(brief[:3000])

    material = (book.user_material or "").strip()
    if material and material not in parts and material not in brief:
        parts.append(material[:2000])

    title = (book.title or "").strip()
    if title and title.lower() not in {t.lower() for t in _PLACEHOLDER_TITLES}:
        if title not in parts:
            parts.append(title)

    seed = "\n".join(parts).strip()
    return seed or title or "未命名主题"


def is_provisional_classification(book: Book) -> bool:
    """True when book still carries create-time default 大众非虚构/入门科普 shell."""
    settings = book.ai_inferred_settings if isinstance(book.ai_inferred_settings, dict) else {}
    if settings.get("classification_confirmed") or settings.get("classification_source") in {
        "user",
        "assistant",
        "inferred",
    }:
        return False
    bt = book.book_type.value if book.book_type else "nonfiction"
    st = (book.style_type or "popular_science").strip()
    return bt == "nonfiction" and st == "popular_science"


def mark_classification_source(book: Book, source: str) -> None:
    settings = dict(book.ai_inferred_settings) if isinstance(book.ai_inferred_settings, dict) else {}
    settings["classification_source"] = source
    if source in {"user", "assistant", "inferred"}:
        settings["classification_confirmed"] = True
    book.ai_inferred_settings = settings


def _normalize_style_key(raw: str) -> str:
    key = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "科普": "popular_science",
        "入门科普": "popular_science",
        "大众科普": "popular_science",
        "实战": "practical_guide",
        "操作": "practical_guide",
        "实用指南": "practical_guide",
        "手册": "reference_tool",
        "工具": "reference_tool",
        "技术手册": "reference_tool",
        "洞察": "insight_opinion",
        "观点": "insight_opinion",
        "教材": "textbook",
        "教科书": "textbook",
        "教学": "textbook",
        "深度": "technical_deep_dive",
        "技术深度": "technical_deep_dive",
        "专著": "technical_deep_dive",
        "研究报告": "technical_deep_dive",
        "博士后": "technical_deep_dive",
        "课题": "technical_deep_dive",
        "评论": "ai_review_commentary",
        "评估": "ai_review_commentary",
    }
    return aliases.get(key, key)


def _coerce_book_type(raw: str) -> BookType | None:
    key = (raw or "").strip().lower()
    if not key:
        return None
    if key in {
        "academic",
        "学术",
        "学术专著",
        "教材",
        "论文",
        "研究报告",
        "博士",
        "硕士",
        "专著",
        "课题",
    }:
        return BookType.academic
    if key in {"nonfiction", "大众非虚构", "非虚构", "科普", "大众"}:
        return BookType.nonfiction
    return None


def _coerce_style(book_type: BookType, raw: str) -> str:
    key = _normalize_style_key(raw)
    allowed = _ACADEMIC_STYLES if book_type == BookType.academic else _NONFICTION_STYLES
    if key in allowed:
        return key
    return "textbook" if book_type == BookType.academic else "popular_science"


def _pair_type_and_style(
    raw_type: str,
    raw_style: str,
    *,
    fallback_type: BookType,
    fallback_style: str,
) -> tuple[BookType, str]:
    """Prefer style→type pairing so academic styles are not crushed into 大众非虚构."""
    style_key = _normalize_style_key(raw_style)
    if style_key in _ACADEMIC_STYLES:
        return BookType.academic, style_key
    if style_key in _NONFICTION_STYLES:
        return BookType.nonfiction, style_key

    book_type = _coerce_book_type(raw_type) or fallback_type
    if not raw_style.strip():
        # Do not silently keep create-time popular_science when type flips to academic
        style = _coerce_style(book_type, fallback_style if fallback_type == book_type else "")
    else:
        style = _coerce_style(book_type, raw_style)
    return book_type, style


def infer_and_apply_book_settings(book: Book, model: str, db: Session | None = None) -> str:
    """Infer book_type / style_type / target_words / audience etc. from project_seed.

    Returns the project_seed used for inference (also for literature / outline).
    """
    seed = resolve_project_seed(book, db)
    client = LLMClient()
    current_bt = book.book_type.value if book.book_type else "nonfiction"
    current_st = book.style_type or "popular_science"
    prompt = f"""根据用户创作意图判断书稿类型与体裁，并推断基础设定。只输出 JSON：
{{
  "book_type": "nonfiction|academic",
  "style_type": "popular_science|practical_guide|reference_tool|insight_opinion|textbook|technical_deep_dive|ai_review_commentary",
  "target_words": 80000,
  "target_audience": "...",
  "disciplines": ["1到3个最需要锁定的学科领域"],
  "discipline_candidates": [
    {{"name": "学科领域名称", "reason": "为什么该领域会影响术语/证据/论证", "ambiguity_note": "需要用户确认的边界，没有则留空"}}
  ],
  "topic_tags": ["..."],
  "citation_style": "apa|gb_t7714|none",
  "topic_brief": "选题要点，非用户原话复述",
  "classification_reason": "一句话说明为何选该一级分类与二级体裁"
}}

类型说明：
- nonfiction + popular_science：大众科普入门
- nonfiction + practical_guide：实战操作指南、how-to
- nonfiction + reference_tool：工具/技术手册、速查手册
- nonfiction + insight_opinion：观念洞察、评论文集式非虚构
- academic + textbook：教材/教学用书、课程配套
- academic + technical_deep_dive：技术深度分析、学术专著、博士后/课题/研究报告
- academic + ai_review_commentary：能力评估与学术评论

重要（反默认偏见）：
- 建书时系统占位默认为 nonfiction + popular_science（大众非虚构/入门科普），这不是结论。
- 当前占位：{current_bt} / {current_st} —— 必须按创作意图重新判断，禁止因为占位而原样输出。
- 出现教材、课程、学术论证、文献综述、博士/硕士/课题、研究报告、技术深度、同行评议语气 → 优先 academic。
- 出现操作步骤、实操手册、工具速查 → nonfiction 对应体裁，不要用 popular_science 凑数。
- 只有意图明确是面向大众的科普入门时，才选 popular_science。

学科领域要求：
- 话题标签可以多个任选；学科领域用于锁定术语解释、证据标准和论证方式，通常 1 个，跨学科最多 3 个
- 不要把普通话题词、热点词或读者群体当作学科领域
- 如果同一名词在不同学科含义不同，在 ambiguity_note 中提示用户确认边界
- 学科领域会影响后续写作与审校，宁可少而准，不要泛化罗列

创作意图：
{seed}
"""
    try:
        out = client.chat_completion(
            [
                {
                    "role": "system",
                    "content": "只输出 JSON。书类必须按创作意图判断，禁止无脑沿用大众非虚构默认。",
                },
                {"role": "user", "content": prompt},
            ],
            model=model,
            max_tokens=1200,
            temperature=0.2,
            disable_thinking=True,
        )
        data = parse_llm_json(out)
    except Exception:
        logger.exception("infer_and_apply_book_settings LLM failed book=%s", book.id)
        data = {}

    fallback_type = book.book_type or BookType.nonfiction
    fallback_style = (book.style_type or "popular_science").strip()
    # When still provisional, do not treat create-time defaults as meaningful fallbacks
    if is_provisional_classification(book) and not data.get("book_type") and not data.get("style_type"):
        fallback_type = BookType.nonfiction
        fallback_style = ""
    book_type, style = _pair_type_and_style(
        str(data.get("book_type") or ""),
        str(data.get("style_type") or ""),
        fallback_type=fallback_type,
        fallback_style=fallback_style,
    )
    book.book_type = book_type
    book.style_type = style
    mark_classification_source(book, "inferred")

    try:
        words = int(data.get("target_words") or 0)
    except (TypeError, ValueError):
        words = 0
    if words < 10_000 or words > 500_000:
        words = _DEFAULT_WORDS.get(book_type, 80_000)
    book.target_words = words

    if not book.target_audience:
        book.target_audience = str(data.get("target_audience") or "对相关主题感兴趣的读者")[:500]
    elif data.get("target_audience") and not (book.target_audience or "").strip():
        book.target_audience = str(data.get("target_audience"))[:500]
    # Always refresh audience when still the generic placeholder from create
    if (book.target_audience or "").strip() in {"", "大众读者", "对相关主题感兴趣的读者"}:
        aud = str(data.get("target_audience") or "").strip()
        if aud:
            book.target_audience = aud[:500]

    disciplines = _normalize_disciplines(data.get("disciplines"))
    candidates = _normalize_discipline_candidates(data.get("discipline_candidates"), disciplines)
    if not disciplines and candidates:
        disciplines = [c["name"] for c in candidates[:3]]
    existing_disciplines = _normalize_disciplines(book.disciplines)
    if not existing_disciplines and not (book.discipline or "").strip() and disciplines:
        book.disciplines = disciplines
        book.discipline = disciplines[0]
    elif existing_disciplines:
        book.disciplines = existing_disciplines
        book.discipline = existing_disciplines[0]
    elif (book.discipline or "").strip():
        book.disciplines = [str(book.discipline).strip()[:100]]

    if not book.topic_tags:
        tags = data.get("topic_tags") or []
        book.topic_tags = [str(t)[:50] for t in tags][:8] if isinstance(tags, list) else []

    if not book.citation_style:
        cs = str(data.get("citation_style") or "apa").lower()
        if cs in ("none", "无", "无需"):
            book.citation_style = None
        elif cs == "gb_t7714":
            book.citation_style = CitationStyle.gb_t7714
        else:
            book.citation_style = CitationStyle.apa

    brief = str(data.get("topic_brief") or "").strip()
    if brief and not (book.topic_brief or "").strip():
        book.topic_brief = brief[:3000]

    prev = dict(book.ai_inferred_settings) if isinstance(book.ai_inferred_settings, dict) else {}
    prev.update(
        {
            "topic_brief": (brief or book.topic_brief or "")[:3000],
            "book_type": book.book_type.value,
            "style_type": book.style_type,
            "target_words": book.target_words,
            "disciplines": list(book.disciplines or []),
            "discipline_candidates": candidates,
            "discipline_confirmation_note": "学科领域用于约束同名术语解释、证据标准和论证方式，避免自造理论、名词或抽象类比。",
            "project_seed_preview": seed[:500],
            "inferred_at": datetime.now(timezone.utc).isoformat(),
            "input_hash": hashlib.sha256(seed.encode()).hexdigest(),
            "classification_source": prev.get("classification_source") or "inferred",
            "classification_confirmed": True,
            "classification_reason": str(data.get("classification_reason") or "").strip()[:500],
        }
    )
    book.ai_inferred_settings = prev
    return seed
