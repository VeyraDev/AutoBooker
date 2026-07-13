"""External person/works search for topic assistant (Stage 6 MVP)."""

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
from app.services.literature_docs import _duckduckgo_lite

logger = logging.getLogger(__name__)


def _paper_to_work(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(item.get("title") or "").strip(),
        "year": item.get("year"),
        "authors": list(item.get("authors") or [])[:6],
        "source": str(item.get("source") or item.get("source_label") or "unknown"),
        "url": item.get("url") or "",
        "abstract_preview": (str(item.get("abstract_preview") or "")[:400] or None),
        "journal": item.get("journal") or item.get("venue") or "",
    }


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


class ExternalSearchService:
    def search_person_works(
        self,
        person_name: str,
        *,
        institution: str | None = None,
        topic: str | None = None,
        rows: int = 12,
    ) -> dict[str, Any]:
        person_name = person_name.strip()
        if not person_name:
            raise ValueError("person_name required")

        query_parts = [person_name]
        if institution:
            query_parts.append(institution.strip())
        if topic:
            query_parts.append(topic.strip())
        query = " ".join(p for p in query_parts if p)

        warnings: list[str] = []
        works: list[dict[str, Any]] = []

        try:
            works.extend(_paper_to_work(p) for p in search_semantic_scholar(query, rows=rows))
        except Exception as exc:
            logger.warning("semantic scholar person search failed: %s", exc)
            warnings.append("Semantic Scholar 检索暂不可用")

        try:
            works.extend(_paper_to_work(p) for p in search_crossref(query, rows=rows))
        except Exception as exc:
            logger.warning("crossref person search failed: %s", exc)
            warnings.append("Crossref 检索暂不可用")

        try:
            agent = LiteratureAgent()
            works.extend(_paper_to_work(p) for p in agent.search(query, rows=rows))
        except Exception as exc:
            logger.warning("literature agent person search failed: %s", exc)

        try:
            works.extend(_paper_to_work(p) for p in search_arxiv(query, rows=min(rows, 8)))
        except Exception as exc:
            logger.warning("arxiv person search failed: %s", exc)

        wiki_snippets: list[str] = []
        try:
            wiki_hits = search_wikipedia(person_name, rows=3)
            for hit in wiki_hits:
                works.append(_paper_to_work(hit))
                if hit.get("abstract_preview"):
                    wiki_snippets.append(str(hit["abstract_preview"]))
        except Exception as exc:
            logger.warning("wikipedia person search failed: %s", exc)
            warnings.append("维基百科检索暂不可用")

        try:
            web_q = f"{person_name} {institution or ''} research books publications".strip()
            for title, url, snippet in _duckduckgo_lite(web_q, limit=3):
                works.append(
                    {
                        "title": title[:300],
                        "year": None,
                        "authors": [person_name],
                        "source": "web",
                        "url": url,
                        "abstract_preview": snippet[:400] if snippet else None,
                        "journal": "Web",
                    }
                )
                if snippet:
                    wiki_snippets.append(snippet[:200])
        except Exception as exc:
            logger.warning("web person search failed: %s", exc)
            warnings.append("网页补充检索暂不可用，建议手动上传资料")

        works = _dedupe_works(works)[: rows + 10]
        if not works:
            warnings.append("未检索到公开作品，请手动上传论文列表或作者简介")

        research_directions = _infer_directions(works, wiki_snippets)
        source_scope = (
            "公开检索范围：Semantic Scholar、Crossref、OpenAlex、arXiv、维基百科、"
            "DuckDuckGo 公开网页摘要；不含付费全文数据库。"
        )

        return {
            "person": person_name,
            "institution": institution,
            "topic": topic,
            "query": query,
            "works": works,
            "research_directions": research_directions,
            "source_scope": source_scope,
            "warnings": warnings,
        }
