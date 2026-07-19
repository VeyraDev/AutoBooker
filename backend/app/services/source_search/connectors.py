"""Connectors and normalization for unified source search."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

from app.config import settings
from app.services.literature_docs import _duckduckgo_lite


@dataclass
class ConnectorBatch:
    source_type: str
    attempted: list[str] = field(default_factory=list)
    successful: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    items: list[dict[str, Any]] = field(default_factory=list)
    degraded: bool = False


def _as_year(value: Any) -> int | None:
    if isinstance(value, int) and 1000 <= value <= 9999:
        return value
    match = re.search(r"(?:19|20)\d{2}", str(value or ""))
    return int(match.group(0)) if match else None


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def _stable_id(provider: str, title: str, url: str, external_id: str = "") -> str:
    raw = "|".join([provider, external_id or url, title]).encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:20]


def citation_metadata(source_type: str, item: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    if not str(item.get("title") or "").strip():
        missing.append("题名")
    has_responsibility = bool(item.get("authors") or []) or bool(
        source_type == "industry_report" and str(item.get("publisher") or "").strip()
    )
    if not has_responsibility:
        missing.append("责任者")
    if not (item.get("year") or item.get("published_at")):
        missing.append("日期")
    if not str(item.get("publisher") or item.get("journal") or "").strip():
        missing.append("出版来源")
    stable = item.get("doi") or item.get("isbn") or item.get("external_id") or item.get("url")
    if not stable:
        missing.append("稳定标识")
    eligible = source_type in {"paper", "book", "industry_report"}
    return eligible and not missing, missing


def normalize_item(raw: dict[str, Any], *, provider: str, source_type: str, degraded: bool = False) -> dict[str, Any]:
    title = str(raw.get("title") or raw.get("name") or "").strip()[:500]
    url = str(raw.get("url") or raw.get("link") or "").strip()
    authors_raw = raw.get("authors") or raw.get("author_name") or []
    if isinstance(authors_raw, str):
        authors = [part.strip() for part in re.split(r"[,，;；]", authors_raw) if part.strip()]
    else:
        authors = [str(value).strip() for value in authors_raw if str(value).strip()]
    publisher_raw = raw.get("publisher") or raw.get("journal") or raw.get("venue") or ""
    if isinstance(publisher_raw, list):
        publisher = str(publisher_raw[0] if publisher_raw else "")
    else:
        publisher = str(publisher_raw or "")
    year = _as_year(raw.get("year") or raw.get("first_publish_year") or raw.get("published_at"))
    published_at = str(raw.get("published_at") or raw.get("published_date") or "").strip() or None
    external_id = str(raw.get("external_id") or raw.get("key") or "").strip()
    doi = str(raw.get("doi") or "").removeprefix("https://doi.org/").strip()
    isbn_raw = raw.get("isbn") or ""
    isbn = str(isbn_raw[0] if isinstance(isbn_raw, list) and isbn_raw else isbn_raw).strip()
    score = raw.get("score", raw.get("relevance", 0.5))
    try:
        relevance = max(0.0, min(1.0, float(score)))
    except (TypeError, ValueError):
        relevance = 0.5
    item: dict[str, Any] = {
        "id": _stable_id(provider, title, url, external_id),
        "title": title or "未命名资料",
        "url": url,
        "snippet": str(raw.get("snippet") or raw.get("content") or raw.get("abstract_preview") or raw.get("abstract") or "")[:1500],
        "authors": authors[:20],
        "publisher": publisher[:500],
        "published_at": published_at,
        "year": year,
        "source_type": source_type,
        "provider": provider,
        "domain": _domain(url),
        "relevance": relevance,
        "credibility_hint": "high" if source_type in {"paper", "government"} else ("medium" if source_type != "web" else "unknown"),
        "document_type": str(raw.get("document_type") or raw.get("type") or source_type),
        "doi": doi,
        "isbn": isbn,
        "external_id": external_id,
        "journal": str(raw.get("journal") or raw.get("venue") or publisher)[:500],
        "citations": raw.get("citations", raw.get("cited_by_count")),
        "degraded": degraded,
    }
    citeability, missing = citation_metadata(source_type, item)
    item["citeability"] = citeability
    item["metadata_missing"] = missing
    return item


def search_tavily(
    query: str,
    *,
    source_type: str,
    rows: int,
    time_from: str | None = None,
    time_to: str | None = None,
) -> list[dict[str, Any]]:
    if not settings.TAVILY_API_KEY.strip():
        raise RuntimeError("Tavily 未配置")
    topic = "news" if source_type == "news" else "general"
    body: dict[str, Any] = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "topic": topic,
        "search_depth": "basic",
        "max_results": min(rows, 20),
        "include_answer": False,
        "include_raw_content": False,
    }
    if topic == "general":
        body["country"] = "china"
    if time_from:
        body["start_date"] = time_from
    if time_to:
        body["end_date"] = time_to
    if source_type == "government":
        body["include_domains"] = ["gov.cn"]
    with httpx.Client(timeout=settings.SOURCE_SEARCH_TIMEOUT_SEC, follow_redirects=True) as client:
        response = client.post(f"{settings.TAVILY_BASE_URL.rstrip('/')}/search", json=body)
        response.raise_for_status()
        data = response.json()
    out: list[dict[str, Any]] = []
    for row in data.get("results") or []:
        out.append(
            normalize_item(
                {
                    "title": row.get("title"),
                    "url": row.get("url"),
                    "snippet": row.get("content"),
                    "score": row.get("score"),
                    "published_at": row.get("published_date"),
                    "authors": row.get("authors") or [],
                    "publisher": _domain(str(row.get("url") or "")),
                    "external_id": row.get("url"),
                },
                provider="tavily",
                source_type=source_type,
            )
        )
    return out


def search_open_library(query: str, *, rows: int) -> list[dict[str, Any]]:
    raw_query = query.strip()
    isbn_match = re.search(r"(?:97[89])?[0-9Xx][0-9Xx\-\s]{8,20}", raw_query)
    if isbn_match:
        query_key = "isbn"
        clean_query = re.sub(r"[^0-9Xx]", "", isbn_match.group(0))
    else:
        clean_query = re.sub(
            r"(?:寻找|查找|推荐资料|哪本书讲|图书|书籍|出版物|ISBN)",
            " ",
            raw_query,
            flags=re.IGNORECASE,
        )
        clean_query = re.sub(r"\s+", " ", clean_query).strip() or raw_query
        if "出版社" in raw_query:
            query_key = "publisher"
            clean_query = clean_query.replace("出版社", "").strip() or raw_query
        else:
            query_key = "title" if len(re.sub(r"\s+", "", clean_query)) < 3 else "q"
    params = {
        query_key: clean_query,
        "limit": min(rows, 30),
        "fields": "key,title,author_name,first_publish_year,publisher,isbn",
    }
    with httpx.Client(timeout=settings.SOURCE_SEARCH_TIMEOUT_SEC, follow_redirects=True) as client:
        response = client.get("https://openlibrary.org/search.json", params=params)
        response.raise_for_status()
        data = response.json()
    out: list[dict[str, Any]] = []
    for row in data.get("docs") or []:
        key = str(row.get("key") or "")
        out.append(
            normalize_item(
                {
                    **row,
                    "url": f"https://openlibrary.org{key}" if key.startswith("/") else "",
                    "external_id": key,
                    "snippet": "Open Library 图书元数据",
                },
                provider="open_library",
                source_type="book",
            )
        )
    return out


def _normalize_many(raw: list[dict[str, Any]], provider: str, source_type: str) -> list[dict[str, Any]]:
    return [normalize_item(row, provider=provider, source_type=source_type) for row in raw]


def _http_client() -> httpx.Client:
    return httpx.Client(
        timeout=settings.SOURCE_SEARCH_TIMEOUT_SEC,
        follow_redirects=True,
        headers={"User-Agent": "AutoBooker/1.0 (https://github.com/VeyraDev/AutoBooker; source-search)"},
    )


def search_academic(connector: str, query: str, *, rows: int) -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    with _http_client() as client:
        if connector == "openalex":
            response = client.get(
                "https://api.openalex.org/works",
                params={"search": query, "per_page": min(rows, 25)},
            )
            response.raise_for_status()
            for item in response.json().get("results") or []:
                location = item.get("primary_location") or {}
                source = location.get("source") or {}
                raw.append(
                    {
                        "title": item.get("title"),
                        "authors": [
                            (entry.get("author") or {}).get("display_name")
                            for entry in item.get("authorships") or []
                            if (entry.get("author") or {}).get("display_name")
                        ],
                        "year": item.get("publication_year"),
                        "journal": source.get("display_name"),
                        "doi": item.get("doi"),
                        "url": item.get("doi") or item.get("id"),
                        "external_id": item.get("id"),
                        "citations": item.get("cited_by_count"),
                        "type": item.get("type"),
                    }
                )
        elif connector == "crossref":
            response = client.get(
                "https://api.crossref.org/works",
                params={"query": query, "rows": min(rows, 30), "sort": "relevance"},
            )
            response.raise_for_status()
            for item in (response.json().get("message") or {}).get("items") or []:
                issued = ((item.get("issued") or {}).get("date-parts") or [[]])[0]
                title = item.get("title") or []
                journal = item.get("container-title") or []
                raw.append(
                    {
                        "title": title[0] if title else "",
                        "authors": [
                            " ".join(part for part in [author.get("given"), author.get("family")] if part)
                            for author in item.get("author") or []
                        ],
                        "year": issued[0] if issued else None,
                        "journal": journal[0] if journal else "",
                        "doi": item.get("DOI"),
                        "url": item.get("URL"),
                        "external_id": item.get("DOI"),
                        "citations": item.get("is-referenced-by-count"),
                        "type": item.get("type"),
                    }
                )
        elif connector == "semantic_scholar":
            response = client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": query,
                    "limit": min(rows, 30),
                    "fields": "paperId,title,year,authors,venue,externalIds,citationCount,url,abstract",
                },
            )
            response.raise_for_status()
            for item in response.json().get("data") or []:
                external = item.get("externalIds") or {}
                raw.append(
                    {
                        "title": item.get("title"),
                        "authors": [author.get("name") for author in item.get("authors") or [] if author.get("name")],
                        "year": item.get("year"),
                        "journal": item.get("venue"),
                        "doi": external.get("DOI"),
                        "url": item.get("url"),
                        "external_id": item.get("paperId"),
                        "citations": item.get("citationCount"),
                        "abstract": item.get("abstract"),
                        "type": "article",
                    }
                )
        elif connector == "arxiv":
            response = client.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": min(rows, 30),
                    "sortBy": "relevance",
                },
            )
            response.raise_for_status()
            root = ElementTree.fromstring(response.text)
            namespace = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", namespace):
                title = entry.findtext("atom:title", default="", namespaces=namespace).strip()
                published = entry.findtext("atom:published", default="", namespaces=namespace)
                url = entry.findtext("atom:id", default="", namespaces=namespace)
                raw.append(
                    {
                        "title": re.sub(r"\s+", " ", title),
                        "authors": [
                            author.findtext("atom:name", default="", namespaces=namespace).strip()
                            for author in entry.findall("atom:author", namespace)
                        ],
                        "year": _as_year(published),
                        "published_at": published[:10] or None,
                        "journal": "arXiv",
                        "url": url,
                        "external_id": url.rstrip("/").split("/")[-1],
                        "abstract": entry.findtext("atom:summary", default="", namespaces=namespace),
                        "type": "preprint",
                    }
                )
        else:
            raise RuntimeError(f"未知学术连接器: {connector}")
    return _normalize_many(raw, connector, "paper")


def search_github_source(query: str, *, rows: int) -> list[dict[str, Any]]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AutoBooker"}
    if settings.GITHUB_TOKEN.strip():
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN.strip()}"
    with httpx.Client(
        timeout=settings.SOURCE_SEARCH_TIMEOUT_SEC,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = client.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": min(rows, 30)},
        )
        response.raise_for_status()
        data = response.json()
    return _normalize_many(
        [
            {
                "title": item.get("full_name") or item.get("name"),
                "authors": [(item.get("owner") or {}).get("login")],
                "year": _as_year(item.get("updated_at")),
                "published_at": item.get("updated_at"),
                "publisher": "GitHub",
                "url": item.get("html_url"),
                "external_id": item.get("full_name"),
                "snippet": item.get("description"),
                "citations": item.get("stargazers_count"),
                "type": "repository",
            }
            for item in data.get("items") or []
        ],
        "github",
        "technical",
    )


def search_wikipedia_source(query: str, *, rows: int) -> list[dict[str, Any]]:
    with _http_client() as client:
        response = client.get(
            "https://zh.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": min(rows, 20),
                "utf8": 1,
                "variant": "zh-cn",
            },
        )
        response.raise_for_status()
        data = response.json()
    return _normalize_many(
        [
            {
                "title": item.get("title"),
                "authors": ["Wikipedia 编辑者"],
                "publisher": "Wikipedia",
                "url": f"https://zh.wikipedia.org/wiki/{str(item.get('title') or '').replace(' ', '_')}",
                "external_id": item.get("pageid") or item.get("title"),
                "snippet": re.sub(r"<[^>]+>", "", str(item.get("snippet") or "")),
                "type": "encyclopedia",
            }
            for item in (data.get("query") or {}).get("search") or []
        ],
        "wikipedia",
        "web",
    )


def execute_connector(
    connector: str,
    *,
    source_type: str,
    query: str,
    rows: int,
    time_from: str | None = None,
    time_to: str | None = None,
) -> ConnectorBatch:
    task_name = f"{connector}:{source_type}"
    batch = ConnectorBatch(source_type=source_type, attempted=[task_name])
    try:
        if connector == "tavily":
            items = search_tavily(
                query,
                source_type=source_type,
                rows=rows,
                time_from=time_from,
                time_to=time_to,
            )
        elif connector == "open_library":
            items = search_open_library(query, rows=rows)
        elif connector in {"openalex", "crossref", "semantic_scholar", "arxiv"}:
            items = search_academic(connector, query, rows=rows)
        elif connector == "github":
            items = search_github_source(query, rows=rows)
        elif connector == "wikipedia":
            items = search_wikipedia_source(query, rows=rows)
        else:
            raise RuntimeError(f"未知连接器: {connector}")
        batch.items = items
        batch.successful.append(task_name)
        return batch
    except Exception as exc:
        batch.failed[task_name] = str(exc)[:300]
        if connector != "tavily" or not settings.SOURCE_SEARCH_ALLOW_DDG_FALLBACK:
            return batch

    fallback_name = f"duckduckgo_lite:{source_type}"
    batch.attempted.append(fallback_name)
    try:
        rows_raw = _duckduckgo_lite(query, limit=min(rows, 8))
        batch.items = [
            normalize_item(
                {"title": title, "url": url, "snippet": snippet, "external_id": url},
                provider="duckduckgo_lite",
                source_type=source_type,
                degraded=True,
            )
            for title, url, snippet in rows_raw
        ]
        batch.successful.append(fallback_name)
        batch.degraded = True
    except Exception as exc:
        batch.failed[fallback_name] = str(exc)[:300]
    return batch
