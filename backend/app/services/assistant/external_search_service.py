"""External person/works search — LLM intent + queries (rule parse is weak fallback only)."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.literature_agent import (
    LiteratureAgent,
    search_arxiv,
    search_crossref,
    search_semantic_scholar,
    search_wikipedia,
)
from app.services.assistant.person_author_rank import build_author_candidates, rank_works_for_person
from app.services.assistant.person_search_intent import PersonSearchIntent
from app.services.assistant.search_intent_service import SearchIntent, prepare_search
from app.services.literature.source_registry import enrich_work_with_registry
from app.services.literature_docs import _duckduckgo_lite

logger = logging.getLogger(__name__)


def _paper_to_work(item: dict[str, Any]) -> dict[str, Any]:
    return enrich_work_with_registry(
        {
            "title": str(item.get("title") or "").strip(),
            "year": item.get("year"),
            "authors": list(item.get("authors") or [])[:6],
            "source": str(item.get("source") or item.get("source_label") or "unknown"),
            "url": item.get("url") or "",
            "abstract_preview": (str(item.get("abstract_preview") or "")[:400] or None),
            "journal": item.get("journal") or item.get("venue") or "",
        }
    )


def _dedupe_works(works: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for w in works:
        key = (w.get("title") or "").lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out


def _infer_directions(works: list[dict[str, Any]], wiki_snippets: list[str]) -> list[str]:
    directions: list[str] = []
    keywords: dict[str, int] = {}
    for w in works[:20]:
        title = str(w.get("title") or "")
        abstract = str(w.get("abstract_preview") or "")
        for token in (title + " " + abstract).replace("，", " ").replace(",", " ").split():
            t = token.strip().lower()
            if len(t) < 4 or t.isdigit():
                continue
            keywords[t] = keywords.get(t, 0) + 1
    ranked = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:8]
    if ranked:
        directions.append("高频主题词：" + "、".join(k for k, _ in ranked[:5]))
    for snip in wiki_snippets[:2]:
        if snip.strip():
            directions.append(snip.strip()[:200])
    return directions[:5]


def _to_rank_intent(intent: SearchIntent) -> PersonSearchIntent:
    """Adapt SearchIntent to ranking helper's expected shape."""
    return PersonSearchIntent(
        search_type=intent.search_type,
        person_name=intent.person_name,
        person_name_raw=intent.person_name_raw or intent.person_name,
        institution=intent.institution,
        role=intent.role,
        topic=intent.topic,
        language=list(intent.language),
        source_types=list(intent.source_types),
        require_author_match=intent.require_author_match,
        display_query=intent.display_query or intent.person_name,
    )


def _coerce_intent(intent: SearchIntent | dict[str, Any] | None) -> SearchIntent | None:
    if intent is None:
        return None
    if isinstance(intent, SearchIntent):
        return intent
    if isinstance(intent, dict):
        return SearchIntent(
            search_type=str(intent.get("search_type") or "person_works"),
            person_name=str(intent.get("person_name") or "").strip(),
            person_name_raw=str(intent.get("person_name_raw") or "").strip(),
            institution=str(intent.get("institution") or "").strip() or None,
            role=str(intent.get("role") or "").strip() or None,
            topic=str(intent.get("topic") or "").strip() or None,
            language=list(intent.get("language") or ["zh", "en"]),
            source_types=list(intent.get("source_types") or ["academic"]),
            require_author_match=bool(intent.get("require_author_match", True)),
            needs_disambiguation=bool(intent.get("needs_disambiguation", False)),
            display_query=str(intent.get("display_query") or "").strip(),
            raw_query=str(intent.get("raw_query") or "").strip(),
        )
    return None


class ExternalSearchService:
    def search_person_works(
        self,
        person_name: str = "",
        *,
        institution: str | None = None,
        topic: str | None = None,
        role: str | None = None,
        query: str | None = None,
        rows: int = 12,
        selected_candidate_id: str | None = None,
        intent: SearchIntent | dict[str, Any] | None = None,
        queries: list[str] | None = None,
        prepare_if_missing: bool = True,
    ) -> dict[str, Any]:
        intent_obj = _coerce_intent(intent)
        query_list = [str(q).strip() for q in (queries or []) if str(q).strip()]

        raw = (query or person_name or "").strip()
        if intent_obj is None or not query_list:
            if not prepare_if_missing:
                raise ValueError("intent and queries required (call prepare_search first)")
            if not raw and intent_obj:
                raw = intent_obj.display_query or intent_obj.person_name
            if not raw:
                raise ValueError("person_name or query required")
            prepared = prepare_search(raw, search_type_hint="person_works")
            if intent_obj is None:
                intent_obj = _coerce_intent(prepared["intent"])
            if not query_list:
                query_list = list(prepared["queries"] or [])

        assert intent_obj is not None
        # Merge explicit slot overrides when caller still passes them
        if institution and not intent_obj.institution:
            intent_obj.institution = institution
        if topic and not intent_obj.topic:
            intent_obj.topic = topic
        if role and not intent_obj.role:
            intent_obj.role = role
        if person_name and not intent_obj.person_name:
            intent_obj.person_name = person_name.strip()

        if not query_list:
            query_list = [intent_obj.display_query or intent_obj.person_name]

        rank_intent = _to_rank_intent(intent_obj)
        primary_query = intent_obj.display_query or query_list[0]

        warnings: list[str] = []
        works: list[dict[str, Any]] = []

        for q in query_list[:3]:
            try:
                works.extend(_paper_to_work(p) for p in search_semantic_scholar(q, rows=max(4, rows // 2)))
            except Exception as exc:
                logger.warning("semantic scholar person search failed: %s", exc)
                warnings.append("Semantic Scholar 检索暂不可用")
                break
            try:
                works.extend(_paper_to_work(p) for p in search_crossref(q, rows=max(4, rows // 2)))
            except Exception as exc:
                logger.warning("crossref person search failed: %s", exc)

        try:
            agent = LiteratureAgent()
            works.extend(_paper_to_work(p) for p in agent.search(primary_query, rows=rows))
        except Exception as exc:
            logger.warning("literature agent person search failed: %s", exc)

        try:
            works.extend(_paper_to_work(p) for p in search_arxiv(primary_query, rows=min(rows, 8)))
        except Exception as exc:
            logger.warning("arxiv person search failed: %s", exc)

        wiki_snippets: list[str] = []
        try:
            wiki_queries = [primary_query]
            for q in query_list:
                if q not in wiki_queries:
                    wiki_queries.append(q)
            for wq in wiki_queries[:3]:
                wiki_hits = search_wikipedia(wq, rows=5)
                for hit in wiki_hits:
                    works.append(_paper_to_work(hit))
                    if hit.get("abstract_preview"):
                        wiki_snippets.append(str(hit["abstract_preview"]))
                if wiki_hits:
                    break
        except Exception as exc:
            logger.warning("wikipedia person search failed: %s", exc)
            warnings.append("维基百科检索暂不可用")

        try:
            web_q = primary_query
            if intent_obj.role and intent_obj.role not in web_q:
                web_q = f"{web_q} {intent_obj.role}"
            web_q = f"{web_q} 著作 OR 论文 OR publications".strip()
            for title, url, snippet in _duckduckgo_lite(web_q, limit=4):
                works.append(
                    enrich_work_with_registry(
                        {
                            "title": title[:300],
                            "year": None,
                            "authors": [intent_obj.person_name],
                            "source": "web",
                            "url": url,
                            "abstract_preview": snippet[:400] if snippet else None,
                            "journal": "Web",
                        }
                    )
                )
                if snippet:
                    wiki_snippets.append(snippet[:200])
        except Exception as exc:
            logger.warning("web person search failed: %s", exc)
            warnings.append("网页补充检索暂不可用，建议手动上传资料")

        works = _dedupe_works(works)
        works = rank_works_for_person(works, rank_intent)[: rows + 10]
        candidates = build_author_candidates(works, rank_intent)

        needs_disambiguation = (
            intent_obj.needs_disambiguation or (len(candidates) > 1 and not selected_candidate_id)
        )
        if selected_candidate_id:
            works = [
                w
                for w in works
                if selected_candidate_id
                in f"{'|'.join(str(a) for a in (w.get('authors') or []))}|{intent_obj.institution or ''}"
                or float(w.get("author_match_score") or 0) >= 0.45
            ] or works

        if not works:
            warnings.append("未检索到公开作品，请手动上传论文列表或作者简介")
        if needs_disambiguation:
            warnings.append("检测到多个可能作者身份，请先确认候选人后再生成选题")

        research_directions = _infer_directions(
            [
                w
                for w in works
                if float(w.get("author_match_score") or 0) >= 0.35
                or float(w.get("person_entity_score") or 0) > 0
            ]
            or works,
            wiki_snippets,
        )
        source_scope = (
            "公开检索范围：Semantic Scholar、Crossref、OpenAlex、arXiv、维基百科、"
            "DuckDuckGo 公开网页摘要；检索词由 LLM SearchIntent→queries 生成，再按人物实体相关性排序。"
        )

        return {
            "person": intent_obj.person_name,
            "person_raw": intent_obj.person_name_raw,
            "institution": intent_obj.institution,
            "topic": intent_obj.topic,
            "role": intent_obj.role,
            "search_intent": intent_obj.to_dict(),
            "query": primary_query,
            "queries": query_list,
            "works": works,
            "candidates": candidates,
            "needs_disambiguation": needs_disambiguation,
            "selected_candidate_id": selected_candidate_id,
            "research_directions": research_directions,
            "source_scope": source_scope,
            "warnings": list(dict.fromkeys(warnings)),
        }
