"""Timeline / roadmap parser.

The parser keeps a domain-specific ``events`` list while also emitting
``nodes``/``edges`` for the current generic structured renderer.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.parse.llm_helpers import call_llm_json, llm_available
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析时间线/路线图 JSON。只输出 JSON：
{
  "title": "短标题",
  "events": [
    {"time":"2017", "label":"Transformer"},
    {"time":"2018", "label":"BERT"}
  ]
}
规则：
1. time 保留年份/季度/阶段；label 只保留事件短名，不要长解释。
2. label 禁止写“左侧节点”“完整时间线”“横向展示”等版式说明。
描述：{text}
"""

_EVENT_RE = re.compile(
    r"(?P<time>(?:19|20)\d{2}|Q[1-4]|第[一二三四五六七八九十]+阶段|阶段\s*\d+)\s*(?:年|季度|阶段)?"
    r"\s*(?:[:：\-—]|\s)?\s*(?P<label>[^，,；;。]+)"
)


def _short(text: str, limit: int = 24) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。")
    return raw[:limit].strip(" ：:，,。")


def _title(intent: DiagramIntent, text: str) -> str:
    raw = intent.title or text
    first = re.split(r"[，,。；;：:\n]", str(raw or ""), 1)[0]
    return _short(first, 24) or "时间线"


def _rule_events(text: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for m in _EVENT_RE.finditer(text):
        time = _short(m.group("time"), 12)
        label = _short(m.group("label"), 22)
        label = re.sub(r"^(完成|上线|添加|发布)\s*", r"\1", label)
        if time and label and not any(e["time"] == time and e["label"] == label for e in events):
            events.append({"time": time, "label": label})
    return events[:12]


def _normalize_events(raw: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        time = _short(item.get("time") or item.get("year") or item.get("quarter") or "", 12)
        label = _short(item.get("label") or item.get("event") or item.get("milestone") or "", 22)
        if time and label:
            out.append({"time": time, "label": label})
    return out[:12]


def _to_graph(title: str, events: list[dict[str, str]]) -> dict[str, Any]:
    nodes = [
        {
            "id": f"e{i}",
            "label": f"{event['time']} {event['label']}",
            "shape": "rounded",
            "level": i,
            "column": 0,
        }
        for i, event in enumerate(events)
    ]
    edges = [{"from": f"e{i}", "to": f"e{i + 1}", "label": ""} for i in range(max(0, len(nodes) - 1))]
    return {
        "diagram_subtype": "timeline_roadmap",
        "layout": "LR" if len(nodes) <= 7 else "TB",
        "title": title,
        "structure_summary": f"{len(events)} 个时间节点",
        "events": events,
        "nodes": nodes,
        "edges": edges,
    }


def parse_timeline(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    if llm_available(ctx):
        data = call_llm_json(ctx, _PROMPT, max_tokens=1600)
        events = _normalize_events(data.get("events") if isinstance(data, dict) else None)
        if events:
            title = _title(intent, str(data.get("title") or ctx.normalized_input))
            return ParsedDiagram(_to_graph(title, events), "llm_timeline")
        return ParsedDiagram({"title": _title(intent, ctx.normalized_input)}, "llm_timeline_failed")
    events = _rule_events(ctx.normalized_input)
    if not events:
        events = [
            {"time": "阶段 1", "label": "启动"},
            {"time": "阶段 2", "label": "建设"},
            {"time": "阶段 3", "label": "发布"},
        ]
    return ParsedDiagram(_to_graph(_title(intent, ctx.normalized_input), events), "rules_timeline")
