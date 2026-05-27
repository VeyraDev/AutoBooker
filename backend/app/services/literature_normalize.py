"""文献条目归一化（避免 literature_agent ↔ literature_docs 循环导入）。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.services.literature_profiles import SOURCE_LABELS


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
    if source == "official_doc" and ext_id:
        return ext_id if ext_id.startswith("http") else (paper.get("url") or "")
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


def normalize_paper(it: dict[str, Any], *, source: str) -> dict[str, Any]:
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
    if it.get("url"):
        paper["url"] = (it.get("url") or "").strip()
    paper["url"] = paper_url(paper)
    return paper
