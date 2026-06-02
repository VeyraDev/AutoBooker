"""AI 检测：第三方 API + 规则降级。"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings

_TEMPLATE_PATTERNS = [
    (r"在当今(?:社会|时代|.*?)?[，,]", "模板化开头"),
    (r"随着.*?的(?:不断)?发展", "模板化开头"),
    (r"综上所述", "空洞过渡"),
    (r"不仅.*?而且.*?不仅", "排比堆砌"),
    (r"研究表明", "无来源断言"),
    (r"有数据显示", "无来源断言"),
    (r"值得注意的是", "模板化过渡"),
]


@dataclass
class AiDetectSegment:
    start: int
    end: int
    score: float
    reasons: list[str] = field(default_factory=list)
    text: str = ""


@dataclass
class AiDetectResult:
    overall_score: float
    provider: str
    segments: list[AiDetectSegment]
    body_hash: str = ""


def _body_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_paragraphs(text: str) -> list[tuple[int, int, str]]:
    parts: list[tuple[int, int, str]] = []
    pos = 0
    for block in re.split(r"\n\n+", text):
        block = block.strip()
        if not block:
            pos += 2
            continue
        start = text.find(block, pos)
        if start < 0:
            start = pos
        end = start + len(block)
        parts.append((start, end, block))
        pos = end
    return parts


class AiDetectProvider(ABC):
    @abstractmethod
    def detect(self, text: str) -> AiDetectResult:
        ...


class RuleBasedAiDetectProvider(AiDetectProvider):
    """内部规则分：模板句、句长方差等。"""

    def detect(self, text: str) -> AiDetectResult:
        segments: list[AiDetectSegment] = []
        scores: list[float] = []
        for start, end, para in _split_paragraphs(text):
            if len(para) < 20:
                continue
            reasons: list[str] = []
            hit = 0
            for pat, label in _TEMPLATE_PATTERNS:
                if re.search(pat, para):
                    reasons.append(label)
                    hit += 1
            sentences = re.split(r"[。！？!?]", para)
            lengths = [len(s) for s in sentences if len(s.strip()) > 4]
            if lengths:
                avg = sum(lengths) / len(lengths)
                var = sum((l - avg) ** 2 for l in lengths) / len(lengths)
                if var < 80 and avg > 25:
                    reasons.append("句式单一")
                    hit += 1
            seg_score = min(95.0, 35.0 + hit * 18.0)
            if hit > 0:
                segments.append(
                    AiDetectSegment(start=start, end=end, score=seg_score, reasons=reasons, text=para[:300])
                )
                scores.append(seg_score)
        overall = sum(scores) / len(scores) if scores else 25.0
        return AiDetectResult(
            overall_score=round(overall, 1),
            provider="rules",
            segments=sorted(segments, key=lambda s: s.score, reverse=True),
            body_hash=_body_hash(text),
        )


class ExternalApiAiDetectProvider(AiDetectProvider):
    """可配置第三方检测 API。"""

    def __init__(self, api_url: str, api_key: str = "") -> None:
        self._url = api_url.rstrip("/")
        self._key = api_key

    def detect(self, text: str) -> AiDetectResult:
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        payload = {"text": text[:50000]}
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(self._url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        segments = []
        for item in data.get("segments") or []:
            segments.append(
                AiDetectSegment(
                    start=int(item.get("start", 0)),
                    end=int(item.get("end", 0)),
                    score=float(item.get("score", 0)),
                    reasons=list(item.get("reasons") or []),
                    text=str(item.get("text") or "")[:300],
                )
            )
        overall = float(data.get("overall_score", data.get("score", 0)))
        return AiDetectResult(
            overall_score=round(overall, 1),
            provider="external",
            segments=segments,
            body_hash=_body_hash(text),
        )


def get_ai_detect_provider() -> AiDetectProvider:
    url = (settings.AI_DETECT_API_URL or "").strip()
    if url:
        return ExternalApiAiDetectProvider(url, settings.AI_DETECT_API_KEY or "")
    return RuleBasedAiDetectProvider()


def result_to_dict(result: AiDetectResult) -> dict[str, Any]:
    return {
        "overall_score": result.overall_score,
        "provider": result.provider,
        "body_hash": result.body_hash,
        "segments": [
            {
                "start": s.start,
                "end": s.end,
                "score": s.score,
                "reasons": s.reasons,
                "text": s.text,
            }
            for s in result.segments
        ],
    }
