"""降重语义保真验证。"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.llm.client import LLMClient

_FACT_LINE_RE = re.compile(r"^\s*[-•\d.]+\s*(.+)$", re.MULTILINE)
_HEADING_SPLIT_RE = re.compile(r"(?m)^(#{1,6}\s+.+)$")


def extract_facts(client: LLMClient, model: str, text: str) -> list[str]:
    """改写前抽取需保留的事实清单。"""
    if not text.strip():
        return []
    system = "你是事实抽取器。只输出 JSON：{\"facts\": [\"...\"]}。每条事实一句，保留数字、结论、术语。"
    user = f"请从以下文本抽取必须保留的事实（数字、因果关系、术语定义、引用相关结论）：\n\n{text[:6000]}"
    try:
        out = client.chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=model,
            max_tokens=1500,
            temperature=0.0,
        )
        from app.utils.json_llm import parse_llm_json

        data = parse_llm_json(out)
        if isinstance(data, dict):
            return [str(x).strip() for x in (data.get("facts") or []) if str(x).strip()][:40]
    except Exception:
        pass
    # fallback: numbers and short claims
    facts: list[str] = []
    for m in re.finditer(r"\d+(?:\.\d+)?%?|\d{4}年", text):
        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 30)
        facts.append(text[start:end].strip())
    return list(dict.fromkeys(facts))[:20]


def verify_facts_preserved(facts: list[str], rewritten: str) -> list[str]:
    missing: list[str] = []
    for fact in facts:
        f = fact.strip()
        if not f:
            continue
        if f in rewritten:
            continue
        ratio = SequenceMatcher(None, f, rewritten).ratio()
        if ratio < 0.45 and not any(tok in rewritten for tok in re.findall(r"\d+(?:\.\d+)?%?", f)):
            missing.append(f)
    return missing


def similarity_score(original: str, rewritten: str) -> float:
    return round(SequenceMatcher(None, original, rewritten).ratio(), 3)


def split_by_headings(text: str, *, fallback_limit: int = 7000) -> list[str]:
    """按 Markdown 标题切分，保留标题上下文。"""
    text = (text or "").strip()
    if not text:
        return []
    parts = _HEADING_SPLIT_RE.split(text)
    chunks: list[str] = []
    current = ""
    for part in parts:
        if not part.strip():
            continue
        if _HEADING_SPLIT_RE.match(part):
            if current.strip():
                chunks.append(current.strip())
            current = part.strip() + "\n\n"
        else:
            current += part
    if current.strip():
        chunks.append(current.strip())
    if not chunks:
        return _split_by_size(text, fallback_limit)
    out: list[str] = []
    for chunk in chunks:
        if len(chunk) > fallback_limit:
            out.extend(_split_by_size(chunk, fallback_limit))
        else:
            out.append(chunk)
    return out or [text]


def _split_by_size(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for para in re.split(r"\n\n+", text):
        chunk_len = len(para) + (2 if buf else 0)
        if buf and size + chunk_len > limit:
            chunks.append("\n\n".join(buf))
            buf = [para]
            size = len(para)
        else:
            buf.append(para)
            size += chunk_len
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks or [text]


def assess_similarity_warnings(score: float) -> list[str]:
    warnings: list[str] = []
    if score > 0.92:
        warnings.append("similarity_too_high_rewrite_ineffective")
    elif score < 0.55:
        warnings.append("similarity_too_low_meaning_drift_risk")
    return warnings
