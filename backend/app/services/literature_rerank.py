"""文献召回后 ReRank 与质量门槛。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_RELEVANCE_THRESHOLD = 4.0


def _text_blob(p: dict[str, Any]) -> str:
    return " ".join(
        [
            p.get("title") or "",
            p.get("abstract_preview") or "",
            p.get("journal") or "",
        ]
    ).casefold()


def apply_must_filters(
    papers: list[dict[str, Any]],
    *,
    must_include: list[str],
    must_exclude: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in papers:
        blob = _text_blob(p)
        if must_exclude and any(x.casefold() in blob for x in must_exclude if x):
            continue
        if must_include and not any(x.casefold() in blob for x in must_include if x):
            continue
        out.append(p)
    if not must_include and not must_exclude:
        return papers
    return out


def quality_gate(p: dict[str, Any], *, profile: str) -> bool:
    src = (p.get("source") or "").lower()
    cites = int(p.get("citations") or 0)
    if src in ("crossref", "semantic_scholar", "arxiv"):
        min_cites = 3 if profile in ("popular", "nonfiction") else 0
        if profile == "academic" and cites < 1 and (p.get("year") or 0) < 2018:
            return False
        if min_cites and cites < min_cites and (p.get("year") or 0) < 2022:
            return False
    if src == "github":
        if profile == "practical" and cites < 3:
            return False
        if profile != "practical" and cites < 10:
            return False
    return True


def rerank_papers(
    query: str,
    papers: list[dict[str, Any]],
    *,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    if not papers or len(papers) <= 2:
        return papers
    items = papers[:40]
    lines = []
    for i, p in enumerate(items):
        lines.append(
            f"{i}. title={p.get('title','')[:120]} | abstract={(p.get('abstract_preview') or '')[:200]}"
        )
    prompt = f"""
对下列文献条目，按与检索词的相关性打分 0-10。只返回 JSON 数组：
[{{"index": 0, "score": 8}}, ...]

检索词：{query}

条目：
{chr(10).join(lines)}
""".strip()
    try:
        client = LLMClient()
        out = client.chat_completion(
            [{"role": "user", "content": prompt}],
            model=settings.intent_model,
            max_tokens=800,
            temperature=0.1,
        )
        data = parse_llm_json(out)
        if isinstance(data, list):
            scores = {int(x.get("index", -1)): float(x.get("score", 0)) for x in data if isinstance(x, dict)}
            scored = []
            for i, p in enumerate(items):
                s = scores.get(i, 5.0)
                if s >= _RELEVANCE_THRESHOLD:
                    scored.append((s, p))
            scored.sort(key=lambda x: x[0], reverse=True)
            ranked = [p for _, p in scored]
            if ranked:
                rest = [p for i, p in enumerate(items) if i not in scores or scores.get(i, 0) < _RELEVANCE_THRESHOLD]
                result = ranked + rest
                return result[:top_n] if top_n else result
    except Exception as e:
        logger.warning("rerank failed: %s", e)
    return papers[:top_n] if top_n else papers
