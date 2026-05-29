"""官方文档最小版检索（HF / PyTorch / OpenAI）。"""

from __future__ import annotations

import logging
import re
from typing import Any
import httpx

from app.services.literature_http import WIKI_HEADERS, literature_client
from app.services.literature_normalize import normalize_paper

logger = logging.getLogger(__name__)

_DOC_SITES = [
    ("Hugging Face", "https://huggingface.co/docs", "huggingface.co/docs"),
    ("PyTorch", "https://pytorch.org/docs/stable/", "pytorch.org/docs"),
    ("OpenAI Platform", "https://platform.openai.com/docs", "platform.openai.com/docs"),
]


def search_official_docs(query: str, rows: int = 8) -> list[dict[str, Any]]:
    """通过 DuckDuckGo HTML 或站点内搜索近似召回文档页（无 API key）。"""
    q = query.strip()
    if not q:
        return []
    out: list[dict[str, Any]] = []
    for label, base_url, site_hint in _DOC_SITES:
        if len(out) >= rows:
            break
        search_q = f"site:{site_hint} {q}"
        try:
            items = _duckduckgo_lite(search_q, limit=3)
        except Exception as e:
            logger.warning("official doc search %s failed: %s", label, e)
            items = []
        for title, url, snippet in items:
            out.append(
                normalize_paper(
                    {
                        "title": title[:300],
                        "year": None,
                        "authors": [label],
                        "journal": f"{label} Documentation",
                        "doi": "",
                        "citations": 0,
                        "type": "documentation",
                        "external_id": url,
                        "abstract_preview": snippet[:500] if snippet else None,
                        "url": url,
                    },
                    source="official_doc",
                )
            )
    return out[:rows]


def _duckduckgo_lite(query: str, limit: int = 3) -> list[tuple[str, str, str]]:
    """解析 DuckDuckGo lite HTML 结果（尽力而为）。"""
    url = "https://lite.duckduckgo.com/lite/"
    with literature_client(timeout=8.0) as client:
        r = client.post(url, data={"q": query}, headers=WIKI_HEADERS)
        r.raise_for_status()
        html = r.text
    # 粗略解析 result link
    links = re.findall(
        r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>',
        html,
        re.I,
    )
    snippets = re.findall(r'<td class="result-snippet"[^>]*>([^<]+)</td>', html, re.I)
    results: list[tuple[str, str, str]] = []
    for i, (href, title) in enumerate(links[:limit]):
        snip = snippets[i] if i < len(snippets) else ""
        results.append((title.strip(), href.strip(), snip.strip()))
    return results
