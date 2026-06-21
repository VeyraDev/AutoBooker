"""Mechanism / principle parser.

Grammar target: inputs, transformations, intermediate representations, outputs,
feedback/cross links, and optional repeated stacks. Domain terms are handled as
semantic clues inside this grammar, not as parser families.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.parse.llm_helpers import call_llm_json, llm_available
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析机制/原理图 JSON。只输出 JSON：
{
  "title": "短标题",
  "inputs": ["输入"],
  "steps": [
    {"id":"m1", "label":"内部机制步骤", "kind":"transform|matrix|stack|attention|feedback"}
  ],
  "outputs": ["输出"],
  "connections": [
    {"from":"input.0", "to":"m1", "label":""}
  ],
  "stacks": [
    {"label":"重复模块", "count":"N", "layers":["子模块A", "子模块B"]}
  ]
}
规则：
1. 表达顺序、层级、嵌套、连接关系；不要只输出 components 平铺列表。
2. steps/layers 只写机制部件短名或动作短语，禁止写“完整机制图”“左侧/右侧”“展示如下”等版式说明。
3. 领域名词只能作为语义线索，不要为每个名词硬套专用模板。
描述：{text}
"""

_TRANSFORMER_ENCODER = ["multi_head_self_attention", "add_norm", "feed_forward", "add_norm"]
_TRANSFORMER_DECODER = [
    "masked_multi_head_self_attention",
    "add_norm",
    "cross_attention",
    "add_norm",
    "feed_forward",
    "add_norm",
]


def _short(text: Any, limit: int = 24) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。")
    raw = re.sub(r"^图\s*\d+\s*[-–—]\s*\d+\s*[:：]\s*", "", raw)
    return raw[:limit].strip(" ：:，,。")


def _title(intent: DiagramIntent, text: str) -> str:
    raw = intent.title or text
    first = re.split(r"[，,。；;：:\n]", str(raw or ""), 1)[0]
    return _short(first, 24) or "机制示意图"


def _layer_count(text: str) -> int:
    m = re.search(r"(\d+)\s*(?:层|次堆叠|次叠加|个编码器层)", text)
    return max(1, min(96, int(m.group(1)))) if m else 6


def _transformer_spec(ctx: PipelineContext, intent: DiagramIntent) -> dict[str, Any]:
    n = _layer_count(ctx.normalized_input)
    title = _title(intent, ctx.normalized_input) or "双栈机制结构图"
    return {
        "diagram_subtype": "transformer",
        "title": title,
        "encoder_layers": n,
        "decoder_layers": n,
        "encoder": {"layers": list(_TRANSFORMER_ENCODER)},
        "decoder": {"layers": list(_TRANSFORMER_DECODER)},
        "connections": [{"from": "encoder.output", "to": "decoder.cross_attention", "type": "cross_attention"}],
        "components": list(dict.fromkeys(_TRANSFORMER_ENCODER + _TRANSFORMER_DECODER + ["residual"])),
        "structure_summary": "机制语法：左右堆叠模块 + 交叉连接",
    }


def _normalize_steps(raw: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for i, item in enumerate(raw[:12]):
        if isinstance(item, str):
            label = _short(item, 22)
            kind = "transform"
            sid = f"m{i}"
        elif isinstance(item, dict):
            label = _short(item.get("label") or item.get("name") or item.get("step"), 22)
            kind = str(item.get("kind") or "transform").strip()
            sid = str(item.get("id") or f"m{i}").strip()
        else:
            continue
        if label:
            out.append({"id": sid, "label": label, "kind": kind})
    return out


def _rule_steps(text: str) -> tuple[list[str], list[dict[str, str]], list[str]]:
    inputs = []
    outputs = []
    if "输入序列" in text or "输入层" in text:
        inputs.append("输入")
    if "输出" in text:
        outputs.append("输出")
    candidates = []
    for token in ["Q", "K", "V", "点积", "注意力权重", "加权求和", "隐藏层", "损失", "梯度更新", "前向传播", "反向传播"]:
        if token in text and token not in candidates:
            candidates.append(token)
    if not candidates:
        parts = re.split(r"→|->|经过|得到|生成|计算|更新", text)
        candidates = [_short(p, 18) for p in parts if _short(p, 18)][:6]
    steps = [{"id": f"m{i}", "label": label, "kind": "attention" if "注意力" in label else "transform"} for i, label in enumerate(candidates[:10])]
    return inputs or ["输入"], steps or [{"id": "m0", "label": "处理机制", "kind": "transform"}], outputs or ["输出"]


def _to_graph(title: str, inputs: list[str], steps: list[dict[str, str]], outputs: list[str], connections: list[dict[str, str]] | None = None, stacks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    for i, label in enumerate(inputs[:3]):
        nodes.append({"id": f"input_{i}", "label": _short(label, 18), "shape": "rounded", "level": 0, "column": i})
    for i, step in enumerate(steps):
        nodes.append({"id": step["id"], "label": step["label"], "shape": "box", "level": i + 1, "column": 0})
    base = len(steps) + 1
    for i, label in enumerate(outputs[:3]):
        nodes.append({"id": f"output_{i}", "label": _short(label, 18), "shape": "rounded", "level": base, "column": i})

    ordered = [n["id"] for n in nodes]
    edges = [{"from": ordered[i], "to": ordered[i + 1], "label": ""} for i in range(max(0, len(ordered) - 1))]
    for conn in connections or []:
        src = str(conn.get("from") or "").replace(".", "_")
        dst = str(conn.get("to") or "").replace(".", "_")
        label = _short(conn.get("label") or conn.get("type") or "", 12)
        if src in ordered and dst in ordered:
            edge = {"from": src, "to": dst, "label": label}
            if edge not in edges:
                edges.append(edge)
    return {
        "diagram_subtype": "mechanism_diagram",
        "layout": "TB",
        "title": title,
        "structure_summary": f"{len(steps)} 个机制步骤",
        "inputs": inputs,
        "steps": steps,
        "outputs": outputs,
        "connections": connections or [],
        "stacks": stacks or [],
        "nodes": nodes,
        "edges": edges,
    }


def parse_mechanism(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    if llm_available(ctx):
        data = call_llm_json(ctx, _PROMPT, max_tokens=2400)
        if isinstance(data, dict):
            inputs = [_short(x, 18) for x in data.get("inputs", []) if _short(x, 18)] if isinstance(data.get("inputs"), list) else []
            steps = _normalize_steps(data.get("steps"))
            outputs = [_short(x, 18) for x in data.get("outputs", []) if _short(x, 18)] if isinstance(data.get("outputs"), list) else []
            if steps:
                return ParsedDiagram(
                    _to_graph(
                        _title(intent, data.get("title") or ctx.normalized_input),
                        inputs or ["输入"],
                        steps,
                        outputs or ["输出"],
                        data.get("connections") or [],
                        data.get("stacks") or [],
                    ),
                    "llm_mechanism",
                )
        return ParsedDiagram({"title": _title(intent, ctx.normalized_input)}, "llm_mechanism_failed")
    inputs, steps, outputs = _rule_steps(ctx.normalized_input)
    return ParsedDiagram(_to_graph(_title(intent, ctx.normalized_input), inputs, steps, outputs), "rules_mechanism")
