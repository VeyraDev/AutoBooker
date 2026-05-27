"""文献检索（多源）与引用格式化。"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree

import httpx

from app.services.literature_classic import classic_queries_for_text
from app.services.literature_docs import search_official_docs
from app.services.literature_normalize import normalize_paper, paper_url
from app.services.literature_profiles import (
    PROFILE_ACADEMIC,
    PROFILE_PRACTICAL,
    PROFILE_POPULAR,
    PROFILE_TECHNICAL,
    source_quota,
)
from app.services.literature_rerank import apply_must_filters, quality_gate, rerank_papers

logger = logging.getLogger(__name__)

CROSSREF_WORKS = "https://api.crossref.org/works"
SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1/paper/search"
_NS_ATOM = {"atom": "http://www.w3.org/2005/Atom"}
from app.services.literature_http import WIKI_HEADERS, literature_client

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _normalize_paper(it: dict[str, Any], *, source: str) -> dict[str, Any]:
    return normalize_paper(it, source=source)


def _crossref_item_to_paper(it: dict[str, Any]) -> dict[str, Any]:
    title_list = it.get("title") or []
    title = title_list[0] if title_list else ""
    issued = (it.get("issued") or {}).get("date-parts") or [[]]
    year = issued[0][0] if issued and issued[0] else None
    authors_raw = it.get("author") or []
    authors: list[str] = []
    for a in authors_raw[:6]:
        fam = a.get("family") or ""
        giv = a.get("given") or ""
        if fam or giv:
            authors.append(f"{giv} {fam}".strip())
    journal = ""
    if it.get("container-title"):
        journal = it["container-title"][0]
    cite_n = int(it.get("is-referenced-by-count") or 0)
    doi = (it.get("DOI") or "").strip()
    return _normalize_paper(
        {
            "title": title,
            "year": year,
            "authors": authors,
            "journal": journal,
            "doi": doi,
            "citations": cite_n,
            "type": it.get("type"),
        },
        source="crossref",
    )


def search_crossref(query: str, rows: int = 30) -> list[dict[str, Any]]:
    """CrossRef：多取一些结果，后续按综合分排序。"""
    params = {
        "query": query,
        "rows": min(rows, 50),
        "sort": "relevance",
        "select": "DOI,title,author,issued,container-title,is-referenced-by-count,type,URL",
    }
    try:
        with literature_client(timeout=25.0) as client:
            r = client.get(CROSSREF_WORKS, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("crossref search failed: %s", e)
        return []

    items = (data.get("message") or {}).get("items") or []
    return [_crossref_item_to_paper(it) for it in items]


def search_semantic_scholar(query: str, rows: int = 30) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "limit": min(rows, 50),
        "fields": "paperId,title,year,authors,venue,externalIds,citationCount,influentialCitationCount,url",
    }
    try:
        with literature_client(timeout=25.0) as client:
            r = client.get(SEMANTIC_SCHOLAR, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("semantic scholar search failed: %s", e)
        return []

    out: list[dict[str, Any]] = []
    for it in data.get("data") or []:
        authors = [a.get("name", "") for a in (it.get("authors") or [])[:6] if a.get("name")]
        ext = it.get("externalIds") or {}
        doi = (ext.get("DOI") or "").strip()
        cite_n = int(it.get("citationCount") or 0)
        infl = int(it.get("influentialCitationCount") or 0)
        combined_cites = cite_n + min(infl, max(cite_n // 2, infl // 3))
        out.append(
            _normalize_paper(
                {
                    "title": it.get("title") or "",
                    "year": it.get("year"),
                    "authors": authors,
                    "journal": it.get("venue") or "",
                    "doi": doi,
                    "citations": combined_cites,
                    "type": "article",
                    "semantic_scholar_id": it.get("paperId") or "",
                },
                source="semantic_scholar",
            )
        )
    return out


def lookup_crossref_by_doi(doi: str) -> dict[str, Any] | None:
    doi = doi.strip().removeprefix("https://doi.org/")
    if not doi:
        return None
    url = f"{CROSSREF_WORKS}/{doi}"
    try:
        with literature_client(timeout=20.0) as client:
            r = client.get(url)
            r.raise_for_status()
            it = r.json().get("message") or {}
    except Exception as e:
        logger.warning("crossref doi lookup failed %s: %s", doi, e)
        return None
    return _crossref_item_to_paper(it)


def _merge_paper_dup(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """合并重复条目：取更高被引数，补全 DOI / 外链。"""
    if int(incoming.get("citations") or 0) > int(existing.get("citations") or 0):
        existing["citations"] = incoming["citations"]
    if not existing.get("doi") and incoming.get("doi"):
        existing["doi"] = incoming["doi"]
    if not existing.get("semantic_scholar_id") and incoming.get("semantic_scholar_id"):
        existing["semantic_scholar_id"] = incoming["semantic_scholar_id"]
    if not existing.get("journal") and incoming.get("journal"):
        existing["journal"] = incoming["journal"]
    if not existing.get("year") and incoming.get("year"):
        existing["year"] = incoming["year"]
    if len(incoming.get("authors") or []) > len(existing.get("authors") or []):
        existing["authors"] = incoming["authors"]
    existing["url"] = paper_url(existing)
    return existing


def _paper_dedupe_key(p: dict[str, Any]) -> str:
    doi = (p.get("doi") or "").lower().strip()
    if doi:
        return f"doi:{doi}"
    src = (p.get("source") or "").lower()
    ext = (p.get("external_id") or "").strip().lower()
    if src and ext:
        return f"{src}:{ext}"
    return (p.get("title") or "").lower()[:120]


def _dedupe_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for p in papers:
        key = _paper_dedupe_key(p)
        if not key:
            continue
        if key in by_key:
            merged = _merge_paper_dup(by_key[key], p)
            if not merged.get("abstract_preview") and p.get("abstract_preview"):
                merged["abstract_preview"] = p["abstract_preview"]
            by_key[key] = merged
        else:
            by_key[key] = dict(p)
    return list(by_key.values())


def composite_score(paper: dict[str, Any], *, current_year: int | None = None) -> float:
    """
    综合排序分：被引量（对数归一化）+ 发表年份（新近性衰减）。
    默认约 55% 被引、45% 年份，兼顾经典高引与近五年新作。
    """
    year = int(paper.get("year") or 0)
    cites = int(paper.get("citations") or 0)
    cy = current_year or datetime.now().year

    if year > 0:
        age = max(0, cy - year)
        recency = max(0.15, 1.0 - age / 12.0)
        if year >= cy - 5:
            recency = min(1.0, recency + 0.12)
    else:
        recency = 0.35

    cite_component = math.log1p(cites) / math.log1p(8000)
    cite_component = min(1.0, cite_component)

    return 0.55 * cite_component + 0.45 * recency


def rank_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cy = datetime.now().year
    scored = [(composite_score(p, current_year=cy), p) for p in papers]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored]


def search_wikipedia(query: str, rows: int = 15, *, lang: str | None = None) -> list[dict[str, Any]]:
    langs = [lang] if lang else (["zh", "en"] if _has_cjk(query) else ["en", "zh"])
    out: list[dict[str, Any]] = []
    for lg in langs:
        if len(out) >= rows:
            break
        api = f"https://{lg}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": min(rows, 20),
            "utf8": 1,
        }
        try:
            with literature_client(timeout=20.0) as client:
                r = client.get(api, params=params, headers=WIKI_HEADERS)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.warning("wikipedia search failed %s: %s", lg, e)
            continue
        for hit in (data.get("query") or {}).get("search") or []:
            title = hit.get("title") or ""
            snippet = re.sub(r"<[^>]+>", "", hit.get("snippet") or "")
            out.append(
                _normalize_paper(
                    {
                        "title": title,
                        "year": None,
                        "authors": ["维基百科编者"],
                        "journal": "Wikipedia",
                        "doi": "",
                        "citations": 0,
                        "type": "encyclopedia",
                        "external_id": title,
                        "abstract_preview": snippet,
                        "wiki_lang": lg,
                    },
                    source="wikipedia",
                )
            )
    return out[:rows]


def search_arxiv(query: str, rows: int = 20) -> list[dict[str, Any]]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(rows, 30),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query"
    try:
        with literature_client(timeout=30.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            root = ElementTree.fromstring(r.text)
    except Exception as e:
        logger.warning("arxiv search failed: %s", e)
        return []

    out: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", _NS_ATOM):
        title_el = entry.find("atom:title", _NS_ATOM)
        title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
        summary_el = entry.find("atom:summary", _NS_ATOM)
        summary = (summary_el.text or "").strip() if summary_el is not None else ""
        published = entry.find("atom:published", _NS_ATOM)
        year = None
        if published is not None and published.text:
            try:
                year = int(published.text[:4])
            except ValueError:
                year = None
        authors: list[str] = []
        for a in entry.findall("atom:author", _NS_ATOM):
            name_el = a.find("atom:name", _NS_ATOM)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())
        arxiv_id = ""
        id_el = entry.find("atom:id", _NS_ATOM)
        if id_el is not None and id_el.text:
            arxiv_id = id_el.text.rstrip("/").split("/")[-1]
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
        out.append(
            _normalize_paper(
                {
                    "title": title,
                    "year": year,
                    "authors": authors[:6],
                    "journal": "arXiv",
                    "doi": "",
                    "citations": 0,
                    "type": "preprint",
                    "external_id": arxiv_id,
                    "abstract_preview": summary[:800] if summary else None,
                },
                source="arxiv",
            )
        )
    return out


def search_github(query: str, rows: int = 15) -> list[dict[str, Any]]:
    from app.config import settings

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AutoBooker"}
    token = (settings.GITHUB_TOKEN or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": min(rows, 30)}
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True, headers=headers) as client:
            r = client.get("https://api.github.com/search/repositories", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("github search failed: %s", e)
        return []

    out: list[dict[str, Any]] = []
    for repo in data.get("items") or []:
        full_name = repo.get("full_name") or ""
        updated = (repo.get("updated_at") or "")[:4]
        year = int(updated) if updated.isdigit() else None
        out.append(
            _normalize_paper(
                {
                    "title": repo.get("name") or full_name,
                    "year": year,
                    "authors": [full_name.split("/")[0]] if "/" in full_name else [],
                    "journal": "GitHub",
                    "doi": "",
                    "citations": int(repo.get("stargazers_count") or 0),
                    "type": "repository",
                    "external_id": full_name,
                    "abstract_preview": (repo.get("description") or "")[:500] or None,
                },
                source="github",
            )
        )
    return out


def format_paper_citation(paper: dict[str, Any], style: str, index: int | None = None) -> str:
    from app.services.citation_formats import format_citation_by_source

    src = (paper.get("source") or "").lower()
    if src in ("github", "wikipedia", "official_doc"):
        return format_citation_by_source(paper, style, index=index)
    authors = "; ".join(paper.get("authors", [])[:3])
    if len(paper.get("authors", [])) > 3:
        authors += " 等" if style == "gb_t7714" else " et al."
    year = paper.get("year") or "n.d."
    title = paper.get("title", "")
    journal = paper.get("journal", "")
    idx = f"[{index}] " if index is not None else ""

    if style == "apa":
        return f"{idx}{authors} ({year}). {title}. {journal}."
    if style == "gb_t7714":
        return f"{idx}{authors}. {title}[J]. {journal}, {year}."
    if style == "chicago":
        return f"{idx}{authors}. \"{title}.\" {journal} ({year})."
    if style == "mla":
        return f"{idx}{authors}. \"{title}.\" {journal}, {year}."
    return f"{idx}{authors} ({year}). {title}."


def _fetch_papers_bundle(queries: list[str], fetch_n: int) -> list[dict[str, Any]]:
    """合并论文源；Semantic Scholar 仅首条 query 调用一次，避免 429。"""
    merged: list[dict[str, Any]] = []
    for i, q in enumerate(queries):
        merged.extend(search_arxiv(q, rows=fetch_n))
        if i == 0:
            merged.extend(search_semantic_scholar(q, rows=fetch_n))
        merged.extend(search_crossref(q, rows=fetch_n))
    return merged


class LiteratureAgent:
    """按体裁 profile 分 Tab 检索；桶内排序与 ReRank。"""

    def search_tabbed(
        self,
        queries: list[str],
        profile: str,
        rows: int = 25,
        *,
        must_include: list[str] | None = None,
        must_exclude: list[str] | None = None,
    ) -> dict[str, Any]:
        primary = (queries[0] if queries else "").strip()
        if not primary and not queries:
            return {
                "papers": [],
                "github": [],
                "wiki": [],
                "official_docs": [],
                "refined_queries": queries,
                "warnings": [],
            }

        quota = source_quota(profile, rows)
        fetch_n = min(max(rows, 20), 40)
        all_q = [q for q in queries if q.strip()] or [primary]
        classic = classic_queries_for_text(" ".join(all_q))
        paper_queries = list(dict.fromkeys(all_q + classic))

        papers_raw: list[dict[str, Any]] = []
        github_raw: list[dict[str, Any]] = []
        wiki_raw: list[dict[str, Any]] = []
        docs_raw: list[dict[str, Any]] = []

        # 限制 query 数量，避免检索过慢导致前端超时
        papers_raw = _fetch_papers_bundle(paper_queries[:2], max(10, quota.papers))
        for q in all_q[:2]:
            github_raw.extend(search_github(q, rows=max(quota.github * 2, 12)))
            wiki_raw.extend(search_wikipedia(q, rows=max(quota.wikipedia * 2, 10)))
            docs_raw.extend(search_official_docs(q, rows=max(4, quota.official_doc * 2)))

        mi = must_include or []
        me = must_exclude or []
        warnings: list[str] = []

        def _finish(
            bucket: list[dict[str, Any]],
            limit: int,
            rerank_q: str,
            *,
            use_llm_rerank: bool = False,
        ) -> list[dict[str, Any]]:
            deduped = _dedupe_papers(bucket)
            filtered = apply_must_filters(deduped, must_include=mi, must_exclude=me)
            gated = [p for p in filtered if quality_gate(p, profile=profile)]
            ranked = rank_papers(gated or filtered)
            if use_llm_rerank and len(ranked) > 2:
                reranked = rerank_papers(rerank_q, ranked, top_n=limit)
            else:
                reranked = ranked
            return reranked[:limit]

        if not papers_raw and profile in (PROFILE_ACADEMIC, PROFILE_POPULAR):
            warnings.append("论文源部分不可用（arXiv/Semantic Scholar 限流或网络问题），已返回其他来源结果。")

        return {
            "papers": _finish(papers_raw, quota.papers, primary, use_llm_rerank=True),
            "github": _finish(github_raw, quota.github, primary, use_llm_rerank=False),
            "wiki": _finish(wiki_raw, quota.wikipedia, primary, use_llm_rerank=False),
            "official_docs": _finish(docs_raw, quota.official_doc, primary, use_llm_rerank=False),
            "refined_queries": queries,
            "warnings": warnings,
        }

    def search_by_profile(self, query: str, profile: str, rows: int = 20) -> list[dict[str, Any]]:
        tabbed = self.search_tabbed([query], profile, rows=rows)
        merged = tabbed["papers"] + tabbed["github"] + tabbed["wiki"] + tabbed["official_docs"]
        return merged[:rows]

    def search(self, query: str, rows: int = 20, *, profile: str | None = None) -> list[dict[str, Any]]:
        prof = profile or PROFILE_ACADEMIC
        return self.search_by_profile(query, prof, rows=rows)

    def format_citation(self, paper: dict[str, Any], style: str, index: int | None = None) -> str:
        return format_paper_citation(paper, style, index=index)
