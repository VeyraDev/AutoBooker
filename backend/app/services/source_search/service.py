"""Orchestration, de-duplication and response semantics for source search."""

from __future__ import annotations

import re
import time
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.config import settings
from app.schemas.source_search import (
    SourceFacetOut,
    SourceSearchExecutionOut,
    SourceSearchIn,
    SourceSearchItemOut,
    SourceSearchOut,
    SourceSearchPlanIn,
    SourceSearchPlanOut,
)
from app.services.literature.source_registry import SOURCE_LABELS, executable_connectors, source_capabilities
from app.services.source_search.connectors import ConnectorBatch, execute_connector
from app.services.source_search.planner import SourceSearchPlanner

logger = logging.getLogger(__name__)


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        query = urlencode(
            [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(("utm_", "spm"))]
        )
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))
    except ValueError:
        return url


def _dedupe_key(item: dict[str, Any]) -> str:
    if item.get("doi"):
        return f"doi:{str(item['doi']).lower()}"
    if item.get("isbn"):
        return f"isbn:{re.sub(r'[^0-9xX]', '', str(item['isbn']))}"
    url = _canonical_url(str(item.get("url") or ""))
    if url:
        return f"url:{url}"
    title = re.sub(r"\W+", "", str(item.get("title") or "").lower())
    return f"title:{title[:160]}"


def _merge_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in items:
        key = _dedupe_key(item)
        if key in {"title:", "url:"}:
            continue
        current = merged.get(key)
        if current is None:
            merged[key] = dict(item)
            continue
        if float(item.get("relevance") or 0) > float(current.get("relevance") or 0):
            item, current = current, dict(item)
            merged[key] = current
        for field in ("snippet", "url", "publisher", "published_at", "year", "doi", "isbn", "journal"):
            if not current.get(field) and item.get(field):
                current[field] = item[field]
        if len(item.get("authors") or []) > len(current.get("authors") or []):
            current["authors"] = item["authors"]
        current["degraded"] = bool(current.get("degraded") and item.get("degraded"))
    return sorted(merged.values(), key=lambda row: float(row.get("relevance") or 0), reverse=True)


def _legacy_item(item: SourceSearchItemOut) -> dict[str, Any]:
    return {
        "title": item.title,
        "year": item.year,
        "authors": item.authors,
        "journal": item.journal or item.publisher,
        "doi": item.doi,
        "citations": item.citations or 0,
        "type": item.document_type or item.source_type,
        "source": item.provider,
        "source_label": item.provider,
        "url": item.url,
        "external_id": item.external_id or item.url,
        "abstract_preview": item.snippet,
        "source_type": item.source_type,
        "provider": item.provider,
        "relevance": item.relevance,
        "credibility_hint": item.credibility_hint,
        "citeability": item.citeability,
        "metadata_missing": item.metadata_missing,
        "degraded": item.degraded,
        "isbn": item.isbn,
        "publisher": item.publisher,
        "published_at": item.published_at,
    }


class UnifiedSourceSearchService:
    def __init__(self) -> None:
        self.planner = SourceSearchPlanner()

    def capabilities(self) -> list[dict[str, Any]]:
        return source_capabilities()

    def plan(self, body: SourceSearchPlanIn, *, book: Any | None = None) -> SourceSearchPlanOut:
        return self.planner.build(body, book=book)

    def search(self, body: SourceSearchIn, *, book: Any | None = None) -> SourceSearchOut:
        started = time.perf_counter()
        plan = body.plan or self.plan(SourceSearchPlanIn.model_validate(body.model_dump()), book=book)
        tasks: list[tuple[str, str, str]] = []
        for source_type in plan.requested_source_types:
            if source_type in plan.unavailable_source_types:
                continue
            query = plan.queries_by_source.get(source_type) or plan.query
            for connector in executable_connectors(source_type):
                tasks.append((connector, source_type, query))

        batches: list[ConnectorBatch] = []
        timed_out: list[str] = []
        executor = ThreadPoolExecutor(max_workers=min(8, max(1, len(tasks))))
        futures = {
            executor.submit(
                execute_connector,
                connector,
                source_type=source_type,
                query=query,
                rows=max(4, min(body.rows, 20)),
                time_from=plan.intent.time_from,
                time_to=plan.intent.time_to,
            ): f"{connector}:{source_type}"
            for connector, source_type, query in tasks
        }
        try:
            for future in as_completed(futures, timeout=max(1.0, settings.SOURCE_SEARCH_TIMEOUT_SEC + 1.0)):
                batches.append(future.result())
        except TimeoutError:
            for future, name in futures.items():
                if not future.done():
                    timed_out.append(name)
                    future.cancel()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        attempted = list(dict.fromkeys(name for batch in batches for name in batch.attempted))
        successful = list(dict.fromkeys(name for batch in batches for name in batch.successful))
        failed: dict[str, str] = {}
        for batch in batches:
            failed.update(batch.failed)
        for name in timed_out:
            failed[name] = "连接器超时"
            if name not in attempted:
                attempted.append(name)

        merged = _merge_items([item for batch in batches for item in batch.items])[: body.rows]
        items = [SourceSearchItemOut.model_validate(item) for item in merged]
        counts = Counter(item.source_type for item in items)
        facets = [
            SourceFacetOut(id=source_type, label=SOURCE_LABELS[source_type], count=counts.get(source_type, 0))
            for source_type in plan.requested_source_types
            if source_type not in plan.unavailable_source_types or counts.get(source_type, 0)
        ]
        degraded = any(batch.degraded for batch in batches)
        warnings: list[str] = []
        if plan.unavailable_source_types:
            labels = "、".join(SOURCE_LABELS[value] for value in plan.unavailable_source_types)
            warnings.append(f"{labels}来源未配置，未参与本次检索。")
        if failed and items:
            warnings.append("部分来源检索失败，已返回其他来源结果。")
        elif failed and not items:
            warnings.append("部分或全部来源暂时无法完成检索，请稍后重试。")
        elif not items and not plan.unavailable_source_types and tasks and len(successful) == len(tasks):
            warnings.append("未找到相关资料。")
        elif not items and plan.unavailable_source_types:
            warnings.append("当前可用连接器不足，暂时无法完成检索。")
        if degraded:
            warnings.append("主网页搜索连接器失败，本次已使用降级来源。")

        execution = SourceSearchExecutionOut(
            requested_source_types=plan.requested_source_types,
            attempted_connectors=attempted,
            successful_connectors=successful,
            failed_connectors=failed,
            unavailable_source_types=plan.unavailable_source_types,
            degraded=degraded,
            duration_ms=int((time.perf_counter() - started) * 1000),
            result_counts=dict(counts),
        )
        logger.info(
            "source_search_execution intent=%s requested=%s attempted=%s success=%s failed=%s degraded=%s duration_ms=%s counts=%s",
            plan.intent.kind,
            plan.requested_source_types,
            attempted,
            successful,
            list(failed),
            degraded,
            execution.duration_ms,
            dict(counts),
        )
        legacy = [_legacy_item(item) for item in items]
        by_type = {source_type: [row for row in legacy if row["source_type"] == source_type] for source_type in SOURCE_LABELS}
        return SourceSearchOut(
            query=plan.query,
            plan=plan,
            items=items,
            facets=facets,
            execution=execution,
            warnings=warnings,
            papers=by_type["paper"],
            github=[row for row in by_type["technical"] if row["provider"] == "github"],
            wiki=[row for row in by_type["web"] if row["provider"] == "wikipedia"],
            official_docs=[row for row in by_type["technical"] if row["provider"] != "github"],
            books=by_type["book"],
            news=by_type["news"],
            government=by_type["government"],
            industry_reports=by_type["industry_report"],
            technical=by_type["technical"],
            web=by_type["web"],
            refined_queries=list(plan.queries_by_source.values()),
            source_hint="；".join(f"{facet.label} {facet.count}" for facet in facets),
        )
