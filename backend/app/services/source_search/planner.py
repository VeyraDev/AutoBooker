"""Deterministic search planner used when no LLM planning step is needed."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.source_search import SourceSearchPlanIn, SourceSearchPlanOut
from app.services.literature.source_registry import executable_connectors, source_capabilities

_RULES: list[tuple[str, tuple[str, ...], list[str]]] = [
    ("government_data", ("政策", "法规", "条例", "政府", "统计局", "官方数据", "人口数据", "经济数据", "公报"), ["government"]),
    ("industry_report", ("行业报告", "研究报告", "市场规模", "白皮书", "蓝皮书", "研报"), ["industry_report"]),
    ("event_news", ("新闻", "事件", "报道", "最新", "最近", "发生", "采访", "访谈", "专访"), ["news", "web"]),
    ("literature", ("论文", "文献", "学术", "研究综述", "期刊", "arxiv", "doi"), ["paper"]),
    ("book", ("图书", "书籍", "出版物", "isbn", "出版社", "哪本书"), ["book"]),
    ("person_works", ("著作", "作品", "代表作", "发表了", "publications", "works by"), ["book", "paper", "web"]),
    (
        "person_profile",
        ("人物", "生平", "履历", "经历", "是谁", "简介", "传记", "总裁", "董事长", "创始人", "企业家"),
        ["web", "news"],
    ),
    ("organization", ("公司", "机构", "协会", "研究院", "官网", "组织"), ["web", "news"]),
    ("technical", ("技术文档", "官方文档", "github", "开源", "api", "sdk", "代码库"), ["technical"]),
]

_PLACEHOLDER_TITLE = re.compile(r"^(?:书稿|新书|未命名(?:书稿|图书)?|无标题)(?:\s*\d+)?$", re.IGNORECASE)


def _detect_intent(query: str) -> tuple[str, list[str], str]:
    lowered = query.lower()
    for kind, signals, source_types in _RULES:
        matched = next((signal for signal in signals if signal.lower() in lowered), None)
        if matched:
            return kind, source_types, f"查询包含“{matched}”信号"
    if re.search(r"[·•][\u4e00-\u9fff]{1,8}", query) or re.match(r"^[\u4e00-\u9fff]{2,4}是谁", query):
        return "person_profile", ["web", "news"], "查询形态接近人物资料"
    return "general_web", ["web"], "未命中特定垂类，按普通资料检索"


def _query_for(source_type: str, query: str) -> str:
    suffixes = {
        "paper": "论文 研究",
        "book": "",
        "news": "新闻 采访 专访 报道",
        "government": "政府 官方 数据 政策",
        "industry_report": "行业报告 白皮书 市场数据",
        "technical": "官方文档 GitHub",
        "web": "",
    }
    suffix = suffixes.get(source_type, "")
    return f"{query} {suffix}".strip()


def _compact_text(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())


def _should_add_context(query: str, context: str, *, placeholder_title: bool = False) -> bool:
    if not context or placeholder_title:
        return False
    query_key = _compact_text(query)
    context_key = _compact_text(context)
    if not query_key or not context_key:
        return False
    if query_key in context_key or context_key in query_key:
        return False
    # Context helps vague searches such as “人口数据”; explicit names and role descriptions
    # should be sent as written so a project title cannot dilute the query.
    return len(query_key) < 12


class SourceSearchPlanner:
    def build(self, body: SourceSearchPlanIn, *, book: Any | None = None) -> SourceSearchPlanOut:
        query = body.query.strip()
        kind, inferred_types, rationale = _detect_intent(query)
        source_types = list(body.requested_source_types or inferred_types)

        context_parts: list[str] = []
        if book is not None and body.scope in {"book", "chapter"}:
            title = str(getattr(book, "title", "") or "").strip()
            if _should_add_context(query, title, placeholder_title=bool(_PLACEHOLDER_TITLE.fullmatch(title))):
                context_parts.append(title)
            if body.scope == "chapter" and body.chapter_index:
                chapter = next(
                    (c for c in (getattr(book, "chapters", None) or []) if c.index == body.chapter_index),
                    None,
                )
                if chapter and _should_add_context(query, str(chapter.title or "")):
                    context_parts.append(chapter.title)
        contextual_query = " ".join([*context_parts, query]).strip()

        caps = {row["id"]: row for row in source_capabilities()}
        unavailable = [source_type for source_type in source_types if not caps.get(source_type, {}).get("available")]
        planned = list(
            dict.fromkeys(
                connector
                for source_type in source_types
                for connector in executable_connectors(source_type)
                if source_type not in unavailable
            )
        )
        person_name = query if kind in {"person_profile", "person_works"} and len(query) <= 40 else None
        organization = query if kind == "organization" and len(query) <= 60 else None
        return SourceSearchPlanOut.model_validate(
            {
                "query": query,
                "scope": body.scope,
                "chapter_index": body.chapter_index,
                "intent": {
                    "kind": kind,
                    "display_query": query,
                    "person_name": person_name,
                    "organization": organization,
                    "topic": query,
                    "source_types": source_types,
                    "time_from": body.time_from,
                    "time_to": body.time_to,
                    "rationale": rationale,
                },
                "queries_by_source": {
                    source_type: _query_for(source_type, contextual_query) for source_type in source_types
                },
                "requested_source_types": source_types,
                "planned_connectors": planned,
                "unavailable_source_types": unavailable,
            }
        )
