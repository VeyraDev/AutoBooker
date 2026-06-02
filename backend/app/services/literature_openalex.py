"""OpenAlex 文献检索。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENALEX_SEARCH = "https://api.openalex.org/works"


def search_openalex(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get(
                OPENALEX_SEARCH,
                params={"search": q, "per_page": min(limit, 25)},
                headers={"User-Agent": "AutoBooker/1.0 (mailto:support@autobooker.local)"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("OpenAlex search failed q=%s", q[:80])
        return []

    out: list[dict[str, Any]] = []
    for item in data.get("results") or []:
        authors = []
        for au in item.get("authorships") or []:
            name = (au.get("author") or {}).get("display_name")
            if name:
                authors.append(name)
        primary = item.get("primary_location") or {}
        source = primary.get("source") or {}
        out.append(
            {
                "title": item.get("title") or "",
                "authors": authors,
                "year": (item.get("publication_year") or None),
                "journal": source.get("display_name") or "",
                "doi": (item.get("doi") or "").replace("https://doi.org/", ""),
                "url": item.get("doi") or item.get("id") or "",
                "cited_by_count": item.get("cited_by_count") or 0,
                "abstract": "",
                "source": "openalex",
                "external_source": "OpenAlex",
            }
        )
    return out
