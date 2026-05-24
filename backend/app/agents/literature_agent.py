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

from app.services.literature_profiles import (
    PROFILE_ACADEMIC,
    PROFILE_NONFICTION,
    PROFILE_TECHNICAL,
    SOURCE_LABELS,
)

logger = logging.getLogger(__name__)

CROSSREF_WORKS = "https://api.crossref.org/works"
SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1/paper/search"
_NS_ATOM = {"atom": "http://www.w3.org/2005/Atom"}
_WIKI_UA = {"User-Agent": "AutoBooker/1.0 (literature search; contact: dev@local)"}

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def paper_url(paper: dict[str, Any]) -> str:
    """生成可跳转的外部链接。"""
    if (paper.get("url") or "").strip():
        return paper["url"].strip()
    source = (paper.get("source") or "").lower()
    ext_id = (paper.get("external_id") or "").strip()
    if source == "wikipedia" and ext_id:
        lang = (paper.get("wiki_lang") or "zh").strip() or "zh"
        return f"https://{lang}.wikipedia.org/wiki/{quote(ext_id.replace(' ', '_'))}"
    if source == "arxiv" and ext_id:
        aid = ext_id.replace("arxiv:", "")
        return f"https://arxiv.org/abs/{aid}"
    if source == "github" and ext_id:
        return f"https://github.com/{ext_id}"
    doi = (paper.get("doi") or "").strip()
    if doi:
        return f"https://doi.org/{doi.removeprefix('https://doi.org/')}"
    ss_id = (paper.get("semantic_scholar_id") or "").strip()
    if ss_id:
        return f"https://www.semanticscholar.org/paper/{ss_id}"
    title = (paper.get("title") or "").strip()
    if title:
        return f"https://scholar.google.com/scholar?q={quote(title)}"
    return ""


def _normalize_paper(it: dict[str, Any], *, source: str) -> dict[str, Any]:
    paper = {
        "title": it.get("title") or "",
        "year": it.get("year"),
        "authors": list(it.get("authors") or []),
        "journal": it.get("journal") or "",
        "doi": (it.get("doi") or "").strip(),
        "citations": int(it.get("citations") or 0),
        "type": it.get("type"),
        "source": source,
        "source_label": SOURCE_LABELS.get(source, source),
        "semantic_scholar_id": (it.get("semantic_scholar_id") or "").strip() or None,
        "external_id": (it.get("external_id") or "").strip() or None,
        "abstract_preview": (it.get("abstract_preview") or "").strip() or None,
        "wiki_lang": it.get("wiki_lang"),
    }
    paper["url"] = paper_url(paper)
    return paper


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
        with httpx.Client(timeout=25.0) as client:
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
        with httpx.Client(timeout=25.0) as client:
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
        with httpx.Client(timeout=20.0) as client:
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
            with httpx.Client(timeout=20.0, headers=_WIKI_UA) as client:
                r = client.get(api, params=params)
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
    url = "http://export.arxiv.org/api/query"
    try:
        with httpx.Client(timeout=30.0) as client:
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
        with httpx.Client(timeout=25.0, headers=headers) as client:
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


class LiteratureAgent:
    """按书类/profile 组合多源检索；综合被引量与年份排序。"""

    def search_by_profile(self, query: str, profile: str, rows: int = 20) -> list[dict[str, Any]]:
        q = query.strip()
        if not q:
            return []
        fetch_n = min(max(rows * 2, 24), 40)
        merged: list[dict[str, Any]] = []

        if profile == PROFILE_NONFICTION:
            merged.extend(search_wikipedia(q, rows=fetch_n))
            merged.extend(search_crossref(q, rows=fetch_n // 2))
        elif profile == PROFILE_ACADEMIC:
            merged.extend(search_arxiv(q, rows=fetch_n))
            merged.extend(search_semantic_scholar(q, rows=fetch_n))
            merged.extend(search_crossref(q, rows=fetch_n))
        elif profile == PROFILE_TECHNICAL:
            merged.extend(search_github(q, rows=fetch_n))
            merged.extend(search_arxiv(q, rows=fetch_n))
        else:
            merged.extend(search_crossref(q, rows=fetch_n))
            merged.extend(search_semantic_scholar(q, rows=fetch_n))

        if _has_cjk(q) and profile in (PROFILE_ACADEMIC, PROFILE_NONFICTION):
            ascii_q = re.sub(r"[\u4e00-\u9fff]+", " ", q).strip()
            if len(ascii_q) >= 3:
                if profile == PROFILE_ACADEMIC:
                    merged.extend(search_arxiv(ascii_q, rows=fetch_n // 2))
                    merged.extend(search_semantic_scholar(ascii_q, rows=fetch_n // 2))
                    merged.extend(search_crossref(ascii_q, rows=fetch_n // 2))
                elif profile == PROFILE_NONFICTION:
                    merged.extend(search_crossref(ascii_q, rows=fetch_n // 2))

        deduped = _dedupe_papers(merged)
        ranked = rank_papers(deduped)
        return ranked[:rows]

    def search(self, query: str, rows: int = 20, *, profile: str | None = None) -> list[dict[str, Any]]:
        prof = profile or PROFILE_ACADEMIC
        return self.search_by_profile(query, prof, rows=rows)

    def format_citation(self, paper: dict[str, Any], style: str, index: int | None = None) -> str:
        return format_paper_citation(paper, style, index=index)
