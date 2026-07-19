"""LLM SearchIntent for assistant retrieval (person / literature)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.prompts.assistant.search_intent import (
    SEARCH_INTENT_PROMPT,
    SEARCH_QUERIES_PERSON_PROMPT,
    SEARCH_QUERIES_LITERATURE_PROMPT,
)
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


@dataclass
class SearchIntent:
    search_type: str = "web"
    person_name: str = ""
    person_name_raw: str = ""
    institution: str | None = None
    role: str | None = None
    topic: str | None = None
    language: list[str] = field(default_factory=lambda: ["zh", "en"])
    source_types: list[str] = field(default_factory=lambda: ["web"])
    require_author_match: bool = False
    needs_disambiguation: bool = False
    display_query: str = ""
    raw_query: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_type": self.search_type,
            "person_name": self.person_name,
            "person_name_raw": self.person_name_raw,
            "institution": self.institution,
            "role": self.role,
            "topic": self.topic,
            "language": list(self.language),
            "source_types": list(self.source_types),
            "require_author_match": self.require_author_match,
            "needs_disambiguation": self.needs_disambiguation,
            "display_query": self.display_query,
            "raw_query": self.raw_query,
        }


def _weak_fallback_intent(raw: str) -> SearchIntent:
    """Weak rule fallback only when LLM fails — not the primary path."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    from app.schemas.source_search import SourceSearchPlanIn
    from app.services.source_search.planner import SourceSearchPlanner

    plan = SourceSearchPlanner().build(SourceSearchPlanIn(query=text))
    kind = plan.intent.kind
    is_person = kind in {"person_profile", "person_works"}
    return SearchIntent(
        search_type=kind,
        person_name=text if is_person else "",
        person_name_raw=text if is_person else "",
        topic=text,
        source_types=list(plan.requested_source_types),
        require_author_match=kind == "person_works",
        display_query=text,
        raw_query=text,
    )


def refine_search_intent(
    raw_query: str,
    *,
    search_type_hint: str | None = None,
    model: str | None = None,
) -> SearchIntent:
    raw = (raw_query or "").strip()
    if not raw:
        raise ValueError("raw_query required")

    hint = (search_type_hint or "").strip() or "auto"
    client = LLMClient()
    prompt = SEARCH_INTENT_PROMPT.format(raw_query=raw, search_type_hint=hint)
    try:
        out = client.chat_completion(
            [{"role": "user", "content": prompt}],
            model=model or settings.intent_model,
            max_tokens=800,
            temperature=0.1,
        )
        data = parse_llm_json(out)
        if not isinstance(data, dict):
            raise ValueError("intent json not object")
    except Exception as exc:
        logger.warning("search intent LLM failed, weak fallback: %s", exc)
        intent = _weak_fallback_intent(raw)
        if hint and hint != "auto":
            intent.search_type = hint
            intent.source_types = {
                "person_profile": ["web", "news"],
                "person_works": ["book", "paper", "web"],
                "literature": ["paper"],
                "book": ["book"],
                "event_news": ["news", "web"],
                "organization": ["web", "news"],
                "government_data": ["government"],
                "industry_report": ["industry_report"],
                "technical": ["technical"],
                "web": ["web"],
            }.get(hint, intent.source_types)
        return intent

    st = str(data.get("search_type") or hint or "web").strip()
    allowed_types = {
        "person_profile", "person_works", "literature", "book", "event_news",
        "organization", "government_data", "industry_report", "technical", "web",
    }
    if st not in allowed_types:
        st = "web"

    person = str(data.get("person_name") or "").strip()
    institution = str(data.get("institution") or "").strip() or None
    role = str(data.get("role") or "").strip() or None
    topic = str(data.get("topic") or "").strip() or None
    languages = data.get("language") if isinstance(data.get("language"), list) else ["zh", "en"]
    source_types = data.get("source_types") if isinstance(data.get("source_types"), list) else ["web"]
    allowed_sources = {"paper", "book", "news", "government", "industry_report", "technical", "web"}
    source_types = [str(value) for value in source_types if str(value) in allowed_sources]
    display = str(data.get("display_query") or "").strip() or raw
    if not person and st in {"person_profile", "person_works"}:
        person = raw

    return SearchIntent(
        search_type=st,
        person_name=person,
        person_name_raw=str(data.get("person_name_raw") or raw).strip() or raw,
        institution=institution,
        role=role,
        topic=topic,
        language=[str(x) for x in languages if str(x).strip()][:4] or ["zh", "en"],
        source_types=source_types[:7] or ["web"],
        require_author_match=bool(data.get("require_author_match", st == "person_works")),
        needs_disambiguation=bool(data.get("needs_disambiguation", False)),
        display_query=display,
        raw_query=raw,
    )


def refine_search_queries(
    intent: SearchIntent | dict[str, Any],
    *,
    model: str | None = None,
) -> list[str]:
    if isinstance(intent, dict):
        intent = SearchIntent(
            search_type=str(intent.get("search_type") or "web"),
            person_name=str(intent.get("person_name") or "").strip(),
            person_name_raw=str(intent.get("person_name_raw") or "").strip(),
            institution=str(intent.get("institution") or "").strip() or None,
            role=str(intent.get("role") or "").strip() or None,
            topic=str(intent.get("topic") or "").strip() or None,
            language=list(intent.get("language") or ["zh", "en"]),
            source_types=list(intent.get("source_types") or ["academic"]),
            display_query=str(intent.get("display_query") or "").strip(),
            raw_query=str(intent.get("raw_query") or "").strip(),
        )

    if intent.search_type not in {"person_profile", "person_works"}:
        prompt = SEARCH_QUERIES_LITERATURE_PROMPT.format(
            raw_query=intent.raw_query or intent.display_query or intent.topic or "",
            topic=intent.topic or "",
            language=", ".join(intent.language),
        )
    else:
        prompt = SEARCH_QUERIES_PERSON_PROMPT.format(
            person_name=intent.person_name,
            institution=intent.institution or "",
            role=intent.role or "",
            topic=intent.topic or "",
            display_query=intent.display_query or intent.raw_query,
            language=", ".join(intent.language),
        )

    client = LLMClient()
    try:
        out = client.chat_completion(
            [{"role": "user", "content": prompt}],
            model=model or settings.intent_model,
            max_tokens=600,
            temperature=0.2,
        )
        data = parse_llm_json(out)
        queries = data.get("refined_queries") if isinstance(data, dict) else None
        if not isinstance(queries, list):
            queries = []
        queries = [str(x).strip() for x in queries if str(x).strip()]
    except Exception as exc:
        logger.warning("search queries LLM failed, weak fallback: %s", exc)
        queries = []

    if not queries:
        queries = _weak_fallback_queries(intent)

    # Person search: do NOT force 3 English fillers
    if intent.search_type in {"person_profile", "person_works"}:
        return list(dict.fromkeys(queries))[:8]

    # Literature: soft prefer some English but no hard filler mandate for person path
    from app.services.literature_query_refiner import _order_queries

    return _order_queries(list(dict.fromkeys(queries)))[:8]


def _weak_fallback_queries(intent: SearchIntent) -> list[str]:
    parts = [
        intent.display_query,
        " ".join(x for x in [intent.institution, intent.person_name, intent.role] if x),
        intent.person_name,
    ]
    if intent.topic:
        parts.append(f"{intent.person_name} {intent.topic}")
    return list(dict.fromkeys(p.strip() for p in parts if p and p.strip()))[:5]


def prepare_search(
    raw_query: str,
    *,
    search_type_hint: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Two-step: intent then queries. Preferred entry for tools."""
    intent = refine_search_intent(raw_query, search_type_hint=search_type_hint, model=model)
    queries = refine_search_queries(intent, model=model)
    return {"intent": intent.to_dict(), "queries": queries}
