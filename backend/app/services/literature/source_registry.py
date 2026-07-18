"""Source registry foundation for citation / literature engine."""

from __future__ import annotations

from typing import Any

# Minimal registry — extend connectors without rewriting LiteraturePanel wholesale.
SOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    "openalex": {
        "name": "OpenAlex",
        "source_type": "paper",
        "credibility_level": "high",
        "metadata": True,
        "fulltext": False,
        "auth_required": False,
        "scopes": ["search", "cite"],
    },
    "crossref": {
        "name": "Crossref",
        "source_type": "paper",
        "credibility_level": "high",
        "metadata": True,
        "fulltext": False,
        "auth_required": False,
        "scopes": ["search", "cite"],
    },
    "semantic_scholar": {
        "name": "Semantic Scholar",
        "source_type": "paper",
        "credibility_level": "high",
        "metadata": True,
        "fulltext": False,
        "auth_required": False,
        "scopes": ["search", "cite"],
    },
    "arxiv": {
        "name": "arXiv",
        "source_type": "paper",
        "credibility_level": "medium",
        "metadata": True,
        "fulltext": True,
        "auth_required": False,
        "scopes": ["search", "cite"],
    },
    "wikipedia": {
        "name": "Wikipedia",
        "source_type": "web",
        "credibility_level": "medium",
        "metadata": True,
        "fulltext": False,
        "auth_required": False,
        "scopes": ["search", "disambiguate"],
    },
    "web": {
        "name": "Web",
        "source_type": "web",
        "credibility_level": "low",
        "metadata": False,
        "fulltext": False,
        "auth_required": False,
        "scopes": ["search"],
    },
    "user_upload": {
        "name": "用户资料",
        "source_type": "user_material",
        "credibility_level": "user",
        "metadata": True,
        "fulltext": True,
        "auth_required": False,
        "scopes": ["cite", "evidence"],
    },
}

SOURCE_TYPE_FILTERS = [
    {"id": "paper", "label": "论文"},
    {"id": "book", "label": "图书"},
    {"id": "government", "label": "政府/政策"},
    {"id": "statistics", "label": "统计数据"},
    {"id": "industry_report", "label": "行业报告"},
    {"id": "newspaper", "label": "报刊"},
    {"id": "web", "label": "普通网页"},
    {"id": "user_material", "label": "用户资料"},
]


def get_source_meta(source_key: str) -> dict[str, Any]:
    key = (source_key or "").strip().lower()
    return dict(SOURCE_REGISTRY.get(key) or {
        "name": source_key or "unknown",
        "source_type": "web",
        "credibility_level": "low",
        "metadata": False,
        "fulltext": False,
        "auth_required": False,
        "scopes": ["search"],
    })


def enrich_work_with_registry(work: dict[str, Any]) -> dict[str, Any]:
    item = dict(work)
    meta = get_source_meta(str(item.get("source") or ""))
    item["source_type"] = meta.get("source_type")
    item["credibility_level"] = meta.get("credibility_level")
    item["source_name"] = meta.get("name")
    return item
