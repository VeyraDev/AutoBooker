"""通用 nodes/edges 结构解析。"""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figure_render.figure_structure import infer_structured_spec
from app.services.figures.parse.fallback import parse_fallback
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PARSE_PROMPT = """将描述解析为适合书籍内页的概念关系图 JSON。

只输出 JSON：
{{
  "layout": "TB|LR",
  "title": "图题，不超过 24 个中文字符",
  "structure_summary": "简述图形结构",
  "nodes": [
    {{"id":"n1","label":"短标签，建议 4-14 个中文字符","shape":"diamond|box|rounded|tag","level":0,"column":0,"parent":"可选"}}
  ],
  "edges": [{{"from":"id","to":"id","label":"可选短标签"}}]
}}

解析规则：
1. 仅处理真正的 concept_diagram / loose concept map / radial concept relation。
2. 若描述明显是流程、时间线、分类树、对比矩阵、系统架构、机制图、数据图，不要强行套概念图；这些应由专用 grammar parser 处理。
3. 抽取 3-7 个核心概念，中心概念 level=0，相关概念 level=1/2。
4. label 必须是概念短名；长解释放在 structure_summary，不要塞进 label。
5. 禁止把“完整、左侧、右侧、上方、用箭头连接、展示如下、图中说明”等版式说明写进 label。
6. 节点总数建议 4-10 个，最多 12 个。

图类型：{family}/{subtype}
章节：{chapter_title}
描述：{text}
"""

_FLOW_SPLIT_RE = re.compile(r"\s*(?:→|->|=>|⇒|经过|最后|最终|然后|接着|再到|到达|返回)\s*")
_TITLE_PREFIX_RE = re.compile(r"^(图\s*\d+\s*[-–—]\s*\d+\s*[:：]\s*)")


def _visual_len(text: str) -> float:
    total = 0.0
    for ch in str(text or ""):
        if "\u4e00" <= ch <= "\u9fff":
            total += 1.0
        elif ch.isspace():
            total += 0.35
        else:
            total += 0.55
    return total


def _short_text(text: str, *, max_units: float = 24, fallback: str = "示意图") -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    raw = _TITLE_PREFIX_RE.sub("", raw).strip(" ：:，,。")
    if not raw:
        return fallback
    first = re.split(r"[，,。；;：:\n]", raw, 1)[0].strip(" ：:，,。")
    candidate = first or raw
    if _visual_len(candidate) <= max_units:
        return candidate
    out = ""
    for ch in candidate:
        if _visual_len(out + ch) > max_units:
            break
        out += ch
    return out.strip(" ：:，,。") or fallback


def _label_text(text: str, *, max_units: float = 34) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。")
    if _visual_len(raw) <= max_units:
        return raw
    out = ""
    for ch in raw:
        if _visual_len(out + ch) > max_units:
            break
        out += ch
    return out.strip(" ：:，,。") or raw[:12]


def _node_order(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(n: dict[str, Any]) -> tuple[int, int, str]:
        try:
            level = int(n.get("level") or 0)
        except (TypeError, ValueError):
            level = 0
        try:
            col = int(n.get("column") or 0)
        except (TypeError, ValueError):
            col = 0
        return level, col, str(n.get("id") or "")

    return sorted(nodes, key=key)


def _clean_structured_spec(spec: dict[str, Any], intent: DiagramIntent) -> dict[str, Any]:
    data = dict(spec or {})
    subtype = intent.diagram_subtype
    data["title"] = _short_text(data.get("title") or intent.title, fallback="示意图")
    nodes_in = data.get("nodes") or []
    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, raw in enumerate(nodes_in):
        if not isinstance(raw, dict):
            continue
        nid = str(raw.get("id") or f"n{i}").strip()
        label = _label_text(raw.get("label") or raw.get("name") or "")
        if not nid or not label or nid in seen:
            continue
        node = dict(raw)
        node["id"] = nid
        node["label"] = label
        nodes.append(node)
        seen.add(nid)

    edges: list[dict[str, str]] = []
    edge_keys: set[tuple[str, str]] = set()
    for raw in data.get("edges") or []:
        if not isinstance(raw, dict):
            continue
        src = str(raw.get("from") or raw.get("source") or "").strip()
        dst = str(raw.get("to") or raw.get("target") or "").strip()
        if src in seen and dst in seen and src != dst and (src, dst) not in edge_keys:
            edges.append({"from": src, "to": dst, "label": str(raw.get("label") or "").strip()[:24]})
            edge_keys.add((src, dst))

    if subtype in {"process_flow", "business_workflow", "timeline_roadmap", "timeline", "roadmap"}:
        ordered = _node_order(nodes)
        for left, right in zip(ordered, ordered[1:]):
            key = (str(left["id"]), str(right["id"]))
            if key not in edge_keys:
                edges.append({"from": key[0], "to": key[1], "label": ""})
                edge_keys.add(key)
        if len(ordered) <= 5:
            data["layout"] = "LR"
        else:
            data["layout"] = "TB"
    elif subtype in {"decision_tree", "decision_flow"}:
        root = nodes[0]["id"] if nodes else ""
        for node in nodes[1:]:
            parent = str(node.get("parent") or "").strip()
            if parent and parent in seen:
                key = (parent, str(node["id"]))
            elif not any(e["to"] == node["id"] for e in edges):
                key = (root, str(node["id"]))
            else:
                continue
            if key[0] and key not in edge_keys:
                edges.append({"from": key[0], "to": key[1], "label": ""})
                edge_keys.add(key)

    data["nodes"] = nodes
    data["edges"] = edges
    return data


def _rule_process_flow(ctx: PipelineContext, intent: DiagramIntent) -> dict[str, Any] | None:
    if intent.diagram_subtype not in {"process_flow", "business_workflow", "timeline_roadmap", "timeline", "roadmap"}:
        return None
    text = ctx.normalized_input.strip()
    if not text:
        return None
    candidate = text
    m = re.search(r"(?:步骤依次为|依次为|流程为|包括)[:：]\s*(.+)", text)
    if m:
        candidate = m.group(1)
    parts = [_label_text(p, max_units=22) for p in _FLOW_SPLIT_RE.split(candidate) if p.strip()]
    parts = [p for p in parts if p and p not in {"共4个步骤", "共 4 个步骤"}]
    if len(parts) < 3:
        return None
    parts = parts[:12]
    nodes = [{"id": f"n{i}", "label": label, "shape": "rounded", "level": i, "column": 0} for i, label in enumerate(parts)]
    edges = [{"from": f"n{i}", "to": f"n{i + 1}", "label": ""} for i in range(len(nodes) - 1)]
    return {
        "layout": "LR" if len(nodes) <= 5 else "TB",
        "title": _short_text(intent.title or text, fallback="流程图"),
        "structure_summary": "规则解析的顺序流程",
        "nodes": nodes,
        "edges": edges,
    }


def parse_generic_graph(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    from app.services.figures.parse.llm_helpers import call_llm_json, llm_available

    if llm_available(ctx):
        prompt = _PARSE_PROMPT.format(
            family=intent.diagram_family,
            subtype=intent.diagram_subtype,
            chapter_title=ctx.chapter_title or "（无）",
            text=ctx.normalized_input[:3000],
        )
        data = call_llm_json(ctx, prompt, max_tokens=4096, temperature=0.15)
        if isinstance(data, dict) and data.get("nodes"):
            if intent.title and not data.get("title"):
                data["title"] = intent.title
            return ParsedDiagram(_clean_structured_spec(data, intent), "llm_generic")
        return ParsedDiagram({"title": intent.title or "示意图"}, "llm_generic_failed")
    rule_flow = _rule_process_flow(ctx, intent)
    if rule_flow:
        return ParsedDiagram(rule_flow, "rules_flow")
    spec = infer_structured_spec(ctx.normalized_input)
    if spec:
        if intent.title and not spec.get("title"):
            spec["title"] = intent.title
        return ParsedDiagram(_clean_structured_spec(spec, intent), "rules_generic")
    return parse_fallback(ctx, intent)
