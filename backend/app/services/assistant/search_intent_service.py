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
    search_type: str = "person_works"
    person_name: str = ""
    person_name_raw: str = ""
    institution: str | None = None
    role: str | None = None
    topic: str | None = None
    language: list[str] = field(default_factory=lambda: ["zh", "en"])
    source_types: list[str] = field(default_factory=lambda: ["academic", "official_institution"])
    require_author_match: bool = True
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
    # Prefer existing parser as last resort, without treating it as capability.
    try:
        from app.services.assistant.person_search_intent import build_person_search_intent

        legacy = build_person_search_intent(text, query=text)
        return SearchIntent(
            search_type="person_works",
            person_name=legacy.person_name,
            person_name_raw=legacy.person_name_raw,
            institution=legacy.institution,
            role=legacy.role,
            topic=legacy.topic,
            language=list(legacy.language),
            source_types=list(legacy.source_types),
            require_author_match=legacy.require_author_match,
            display_query=legacy.display_query or text,
            raw_query=text,
        )
    except Exception:
        return SearchIntent(
            search_type="person_works",
            person_name=text,
            person_name_raw=text,
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
        if hint in {"person_works", "literature"}:
            intent.search_type = hint
        return intent

    st = str(data.get("search_type") or hint or "person_works").strip()
    if st not in {"person_works", "literature", "web"}:
        st = "person_works" if hint != "literature" else "literature"

    person = str(data.get("person_name") or "").strip()
    institution = str(data.get("institution") or "").strip() or None
    role = str(data.get("role") or "").strip() or None
    topic = str(data.get("topic") or "").strip() or None
    languages = data.get("language") if isinstance(data.get("language"), list) else ["zh", "en"]
    source_types = (
        data.get("source_types")
        if isinstance(data.get("source_types"), list)
        else ["academic", "official_institution"]
    )
    display = str(data.get("display_query") or "").strip() or raw
    if not person and st == "person_works":
        person = raw

    return SearchIntent(
        search_type=st,
        person_name=person or raw,
        person_name_raw=str(data.get("person_name_raw") or raw).strip() or raw,
        institution=institution,
        role=role,
        topic=topic,
        language=[str(x) for x in languages if str(x).strip()][:4] or ["zh", "en"],
        source_types=[str(x) for x in source_types if str(x).strip()][:6]
        or ["academic", "official_institution"],
        require_author_match=bool(data.get("require_author_match", True)),
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
            search_type=str(intent.get("search_type") or "person_works"),
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

    if intent.search_type == "literature":
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
    if intent.search_type != "literature":
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
