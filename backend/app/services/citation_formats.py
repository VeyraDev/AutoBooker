"""按来源类型生成正文与书末引用格式。"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def format_citation_by_source(
    paper: dict[str, Any],
    style: str,
    index: int | None = None,
) -> str:
    src = (paper.get("source") or "").lower()
    idx = f"[{index}] " if index is not None else ""
    year = paper.get("year") or datetime.now().year
    title = paper.get("title") or ""
    url = (paper.get("url") or "").strip()
    authors = paper.get("authors") or []
    access_year = datetime.now().year

    if src == "github":
        owner = authors[0] if authors else "Unknown"
        repo = title
        ext = (paper.get("external_id") or "").strip()
        if "/" in ext:
            owner, repo = ext.split("/", 1)
        line = f"{idx}{owner}. {repo} ({access_year}). GitHub repository."
        if url:
            line += f" {url}"
        return line

    if src == "wikipedia":
        lang = paper.get("wiki_lang") or "zh"
        line = f"{idx}Wikipedia. {title} ({access_year})."
        if url:
            line += f" {url}"
        elif ext_id := (paper.get("external_id") or "").strip():
            line += f" https://{lang}.wikipedia.org/wiki/{ext_id.replace(' ', '_')}"
        return line

    if src == "official_doc":
        vendor = authors[0] if authors else "Documentation"
        line = f"{idx}{vendor}. {title}."
        if url:
            line += f" {url} (accessed {access_year})."
        return line

    # fallback journal-like
    auth = "; ".join(authors[:3])
    journal = paper.get("journal") or ""
    return f"{idx}{auth} ({year}). {title}. {journal}."


def format_in_text_by_source(
    paper: dict[str, Any],
    style: str,
    *,
    list_index: int | None = None,
) -> str:
    src = (paper.get("source") or "").lower()
    year = paper.get("year") or datetime.now().year
    if style == "gb_t7714" and list_index:
        return f"[{list_index}]"
    if src == "github":
        ext = (paper.get("external_id") or "").strip()
        repo = ext.split("/")[-1] if "/" in ext else (paper.get("title") or "repo")
        owner = ext.split("/")[0] if "/" in ext else ((paper.get("authors") or ["GitHub"])[0])
        return f"({owner}, {repo}, {year})"
    if src == "wikipedia":
        return f"(Wikipedia, {paper.get('title') or '词条'}, {year})"
    if src == "official_doc":
        vendor = (paper.get("authors") or ["Doc"])[0]
        return f"({vendor}, {paper.get('title') or '文档'}, {year})"
    authors = paper.get("authors") or []
    first = authors[0].split()[-1] if authors else "Anonymous"
    return f"({first}, {year})"
