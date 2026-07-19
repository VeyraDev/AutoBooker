"""Executable capability registry for unified source search."""

from __future__ import annotations

from typing import Any

from app.config import settings

SOURCE_LABELS: dict[str, str] = {
    "paper": "论文",
    "book": "图书",
    "news": "新闻/访谈",
    "government": "政府/政策",
    "industry_report": "行业报告",
    "technical": "技术资料",
    "web": "普通网页",
}

SOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    "openalex": {"name": "OpenAlex", "source_types": ["paper"], "executor": "academic"},
    "crossref": {"name": "Crossref", "source_types": ["paper"], "executor": "academic"},
    "semantic_scholar": {"name": "Semantic Scholar", "source_types": ["paper"], "executor": "academic"},
    "arxiv": {"name": "arXiv", "source_types": ["paper"], "executor": "academic"},
    "open_library": {"name": "Open Library", "source_types": ["book"], "executor": "open_library"},
    "github": {"name": "GitHub", "source_types": ["technical"], "executor": "github"},
    "wikipedia": {"name": "Wikipedia", "source_types": ["web"], "executor": "wikipedia"},
    "tavily": {
        "name": "Tavily",
        "source_types": ["book", "news", "government", "industry_report", "technical", "web"],
        "executor": "tavily",
        "requires": "TAVILY_API_KEY",
    },
    "duckduckgo_lite": {
        "name": "DuckDuckGo Lite",
        "source_types": ["book", "news", "government", "industry_report", "technical", "web"],
        "executor": "duckduckgo_lite",
        "fallback_only": True,
    },
    "user_upload": {"name": "用户资料", "source_types": ["user_material"], "executor": "upload"},
}

SOURCE_CONNECTORS: dict[str, list[str]] = {
    "paper": ["openalex", "crossref", "semantic_scholar", "arxiv"],
    "book": ["open_library", "tavily"],
    "news": ["tavily"],
    "government": ["tavily"],
    "industry_report": ["tavily"],
    "technical": ["github", "tavily"],
    "web": ["tavily", "wikipedia"],
}


def _tavily_available() -> bool:
    return bool(
        settings.SOURCE_SEARCH_ENABLED
        and settings.SEARCH_PROVIDER.strip().lower() == "tavily"
        and settings.TAVILY_API_KEY.strip()
    )


def connector_available(connector: str) -> tuple[bool, str | None]:
    if not settings.SOURCE_SEARCH_ENABLED:
        return False, "资料搜索功能未启用"
    if connector == "tavily" and not _tavily_available():
        return False, "Tavily 未配置"
    if connector == "duckduckgo_lite":
        return False, "仅在 Tavily 调用失败时降级使用"
    return connector in SOURCE_REGISTRY, None


def executable_connectors(source_type: str) -> list[str]:
    return [name for name in SOURCE_CONNECTORS.get(source_type, []) if connector_available(name)[0]]


def source_capabilities() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for source_type, label in SOURCE_LABELS.items():
        connectors = executable_connectors(source_type)
        available = bool(connectors)
        reason = None
        if not available:
            configured = SOURCE_CONNECTORS.get(source_type, [])
            reasons = [connector_available(name)[1] for name in configured if connector_available(name)[1]]
            reason = "；".join(dict.fromkeys(reasons)) or "没有已接通的检索连接器"
        elif source_type in {"news", "government", "industry_report", "web"} and not _tavily_available():
            # Wikipedia is supplemental and must not make the general web group look configured.
            available = False
            connectors = []
            reason = "Tavily 未配置"
        out.append(
            {
                "id": source_type,
                "label": label,
                "available": available,
                "connectors": connectors,
                "unavailable_reason": reason,
            }
        )
    return out


SOURCE_TYPE_FILTERS = [{"id": key, "label": label} for key, label in SOURCE_LABELS.items()]


def get_source_meta(source_key: str) -> dict[str, Any]:
    key = (source_key or "").strip().lower()
    raw = SOURCE_REGISTRY.get(key)
    if not raw:
        return {
            "name": source_key or "unknown",
            "source_type": "web",
            "credibility_level": "unknown",
            "metadata": False,
            "scopes": ["search"],
        }
    source_types = raw.get("source_types") or ["web"]
    return {
        **raw,
        "source_type": source_types[0],
        "credibility_level": "high" if source_types[0] in {"paper", "government"} else "medium",
        "metadata": source_types[0] in {"paper", "book", "industry_report"},
        "scopes": ["search", "cite"] if source_types[0] in {"paper", "book", "industry_report"} else ["search"],
    }


def enrich_work_with_registry(work: dict[str, Any]) -> dict[str, Any]:
    item = dict(work)
    meta = get_source_meta(str(item.get("source") or item.get("provider") or ""))
    item.setdefault("source_type", meta.get("source_type"))
    item["credibility_level"] = meta.get("credibility_level")
    item["source_name"] = meta.get("name")
    return item
