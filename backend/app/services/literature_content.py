"""抓取文献可引用正文片段（维基 / arXiv / GitHub / 摘要）。"""

from __future__ import annotations

import logging
import re
from typing import Any
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

_NS_ATOM = {"atom": "http://www.w3.org/2005/Atom"}
_MAX_SNIPPET = 1200


def _trim_snippet(text: str, max_len: int = _MAX_SNIPPET) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= max_len:
        return t
    cut = t[:max_len]
    for sep in ("。", ". ", "；", "; "):
        pos = cut.rfind(sep)
        if pos > max_len // 2:
            return cut[: pos + 1].strip()
    return cut.rstrip() + "…"


def fetch_wikipedia_snippet(title: str, *, lang: str = "zh") -> str:
    if not title.strip():
        return ""
    api = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "explaintext": 1,
        "exintro": 1,
        "titles": title.strip(),
        "redirects": 1,
    }
    headers = {"User-Agent": "AutoBooker/1.0 (literature citation; contact: dev@local)"}
    try:
        with httpx.Client(timeout=20.0, headers=headers) as client:
            r = client.get(api, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("wikipedia extract failed %s: %s", title, e)
        return ""
    pages = (data.get("query") or {}).get("pages") or {}
    for _pid, page in pages.items():
        extract = (page.get("extract") or "").strip()
        if extract:
            return _trim_snippet(extract)
    return ""


def fetch_arxiv_abstract(arxiv_id: str) -> str:
    aid = (arxiv_id or "").strip().replace("arxiv:", "")
    if not aid:
        return ""
    url = f"http://export.arxiv.org/api/query?id_list={aid}"
    try:
        with httpx.Client(timeout=25.0) as client:
            r = client.get(url)
            r.raise_for_status()
            root = ElementTree.fromstring(r.text)
    except Exception as e:
        logger.warning("arxiv fetch failed %s: %s", aid, e)
        return ""
    summary = root.find(".//atom:summary", _NS_ATOM)
    if summary is not None and summary.text:
        return _trim_snippet(summary.text)
    return ""


def fetch_github_readme(repo_full_name: str) -> str:
    """owner/repo"""
    name = (repo_full_name or "").strip().strip("/")
    if "/" not in name:
        return ""
    url = f"https://api.github.com/repos/{name}/readme"
    headers = {
        "Accept": "application/vnd.github.raw",
        "User-Agent": "AutoBooker",
    }
    from app.config import settings

    token = getattr(settings, "GITHUB_TOKEN", "") or ""
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True) as client:
            r = client.get(url)
            if r.status_code == 404:
                return ""
            r.raise_for_status()
            text = r.text
    except Exception as e:
        logger.warning("github readme failed %s: %s", name, e)
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    body = " ".join(lines[:40])
    return _trim_snippet(body) or _trim_snippet(text[:2000])


def fetch_semantic_scholar_abstract(paper_id: str) -> str:
    if not paper_id:
        return ""
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
    params = {"fields": "abstract"}
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("s2 abstract failed %s: %s", paper_id, e)
        return ""
    return _trim_snippet(data.get("abstract") or "")


def fetch_paper_quotable_snippet(paper: dict[str, Any]) -> tuple[str, str]:
    """
    返回 (snippet, fetch_status)。
    fetch_status: ok | partial | failed
    """
    source = (paper.get("source") or "").lower()
    ext_id = (paper.get("external_id") or "").strip()
    preview = (paper.get("abstract_preview") or "").strip()

    if source == "wikipedia" and ext_id:
        sn = fetch_wikipedia_snippet(ext_id)
        if sn:
            return sn, "ok"
    if source == "arxiv" and ext_id:
        sn = fetch_arxiv_abstract(ext_id)
        if sn:
            return sn, "ok"
    if source == "github" and ext_id:
        sn = fetch_github_readme(ext_id)
        if sn:
            return sn, "ok"
    if source == "semantic_scholar":
        pid = ext_id or (paper.get("semantic_scholar_id") or "")
        if pid:
            sn = fetch_semantic_scholar_abstract(pid)
            if sn:
                return sn, "ok"
    if preview:
        return _trim_snippet(preview), "partial"
    doi = (paper.get("doi") or "").strip()
    if doi:
        from app.agents.literature_agent import lookup_crossref_by_doi

        meta = lookup_crossref_by_doi(doi)
        if meta and meta.get("abstract_preview"):
            return _trim_snippet(meta["abstract_preview"]), "partial"
    title = (paper.get("title") or "").strip()
    journal = (paper.get("journal") or "").strip()
    authors = "; ".join((paper.get("authors") or [])[:2])
    year = paper.get("year") or ""
    fallback = f"{authors}（{year}）在《{journal or title}》中讨论了相关主题。"
    if title and len(fallback) > 20:
        return _trim_snippet(fallback), "partial"
    return "", "failed"


def _unescape_snippet(text: str) -> str:
    import html

    s = html.unescape((text or "").strip())
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _body_source_label(source: str, source_label: str) -> str:
    src = (source or "").lower()
    if src == "wikipedia":
        return "维基百科"
    if src == "github":
        return "GitHub"
    if src == "official_doc":
        return source_label or "官方文档"
    if src in ("crossref", "semantic_scholar", "arxiv"):
        return source_label or "文献"
    return source_label or "资料"


def build_quote_paragraph(
    *,
    in_text_mark: str,
    snippet: str,
    source_label: str,
    title: str,
    source: str = "",
) -> str:
    """生成可插入正文的叙述句（不含 APA 括号标记，仅自然表述 + 摘录）。"""
    body = _unescape_snippet(snippet)
    label = _body_source_label(source, source_label)
    t = (title or "").strip()
    if not body:
        if t:
            return f"{label}《{t}》可作为本章参考。"
        return ""
    if label == "维基百科" and t:
        return f"维基百科《{t}》指出：「{body}」"
    if t:
        return f"据{label}《{t}》记载：「{body}」"
    return f"据{label}记载：「{body}」"
