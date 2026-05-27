"""经典论文概念 → 定向检索查询。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import json

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "classic_papers.json"
_CACHE: dict[str, list[dict[str, str]]] | None = None


def _load() -> dict[str, list[dict[str, str]]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
        concepts = raw.get("concepts") or {}
        _CACHE = {str(k).lower(): list(v or []) for k, v in concepts.items()}
    except Exception as e:
        logger.warning("classic_papers.json load failed: %s", e)
        _CACHE = {}
    return _CACHE


def classic_queries_for_text(text: str) -> list[str]:
    """从 query/标题中检测概念并返回额外检索词（论文标题）。"""
    lower = (text or "").casefold()
    concepts = _load()
    out: list[str] = []
    for key, papers in concepts.items():
        if key in lower or key.replace("-", " ") in lower:
            for p in papers:
                t = (p.get("title") or "").strip()
                if t and t not in out:
                    out.append(t)
    return out[:6]
