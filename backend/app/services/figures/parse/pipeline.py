"""Pipeline / workflow parser.

This is a grammar parser: it extracts ordered stages, branches, and feedback
links without caring whether the domain is registration, training, RAG, or ops.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.parse.flow_rules import build_default_flow_edges
from app.services.figures.semantic.flow_semantic import infer_grammar_stages_from_text
from app.services.figures.parse.llm_helpers import call_llm_json, llm_available
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext

_PROMPT = """解析流程/流水线 JSON。只输出 JSON：
{
  "title": "短标题",
  "stages": [
    {"id":"s1", "label":"步骤短名", "kind":"step|decision|parallel|output", "level":0, "column":0}
  ],
  "edges": [
    {"from":"s1", "to":"s2", "label":""}
  ],
  "feedback": [
    {"from":"s5", "to":"s2", "label":"不达标"}
  ]
}
规则：
1. 按语义动作输出 stages，不要按逗号机械切割；合并重复修饰词，但不要合并真实步骤。
2. 如果描述说“4 个步骤/四个阶段”，通常应输出对应数量的语义步骤。
3. stage.label 只写动作或状态短语，如“用户提问”“向量化”“检索知识库”；禁止写“完整流程”“左侧模块”“用箭头连接”“展示如下”等版式说明。禁止写"网关连接前三个服务""通过消息队列异步通知""包含五个模块"等聚合描述——这些是 edges，不是 stage.label。
4. A→B 必须有边；有“返回/重试/不达标”时输出 feedback。
5. 并行分支使用相同 level、不同 column；汇合节点放下一层；反馈边不要新建“返回说明”节点。
描述：{text}
"""

_ARROW_RE = re.compile(r"\s*(?:→|->|=>|⇒|然后|接着|再到|到达|最终|最后)\s*")
_LIST_RE = re.compile(r"[、,，；;]|(?:\s+\d+[.、])|(?:[（(]?\d+[）)]\s*)")
_COUNT_WORDS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _short(text: Any, limit: int = 24) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。")
    raw = re.sub(r"^图\s*\d+\s*[-–—]\s*\d+\s*[:：]\s*", "", raw)
    return raw[:limit].strip(" ：:，,。")


def _title(intent: DiagramIntent, text: str) -> str:
    raw = intent.title or text
    first = re.split(r"[，,。；;：:\n]", str(raw or ""), 1)[0]
    return _short(first, 24) or "流程图"


def _stage_kind(label: str) -> str:
    if re.search(r"是否|判断|若|如果|达标|不达标", label):
        return "decision"
    if re.search(r"输出|返回|完成|结果", label):
        return "output"
    if re.search(r"并行|同时|分支", label):
        return "parallel"
    return "step"


def _expected_count(text: str) -> int | None:
    m = re.search(r"(?:共|包含|包括|分为|有)?\s*(\d{1,2})\s*(?:个)?(?:步骤|阶段|环节|节点|模块)", text)
    if m:
        return max(1, min(20, int(m.group(1))))
    m = re.search(r"(?:共|包含|包括|分为|有)?\s*([一二两三四五六七八九十])\s*(?:个)?(?:步骤|阶段|环节|节点|模块)", text)
    if m:
        return _COUNT_WORDS.get(m.group(1))
    return None


def _sequence_clause(text: str) -> str:
    candidate = text
    m = re.search(r"(?:步骤依次为|依次为|流程为|链路为|路径为|阶段为|环节为|包括|包含)[:：]?\s*(.+)", text)
    if m:
        candidate = m.group(1)
    title_then_from = re.search(r"(?:流程|流程图|图)\s*[，,：:]\s*(从.+)", candidate)
    if title_then_from:
        candidate = title_then_from.group(1)
    if re.search(r"[:：]", candidate):
        before, after = re.split(r"[:：]", candidate, 1)
        if re.search(r"→|->|=>|⇒|、|,|，|；|;", after) or _expected_count(before + after):
            candidate = after
    candidate = re.split(r"(?:，|,|；|;)?\s*(?:用|以|通过)?(?:箭头|连线|方框|节点|图中|每个|共\d|共[一二两三四五六七八九十])", candidate, 1)[0]
    return candidate.strip(" ：:，,。；;")


def _clean_stage_label(text: str) -> str:
    label = _short(text, 22)
    label = re.sub(r"^(?:第?[一二两三四五六七八九十\d]+(?:步|阶段|环节|节点)?[：:、.)）\s]*)", "", label).strip()
    label = re.sub(r"^(?:从|经过|最终|最后|然后|接着|再到|汇合后|汇合后进行|进行)", "", label).strip()
    label = re.sub(r"(?:开始|步骤)$", "", label).strip()
    label = re.sub(r"(?:两个|两条|多个)?并行分支$", "", label).strip()
    label = re.sub(r"(?:流程图|示意图|pipeline|Pipeline)$", "", label).strip(" ：:，,。")
    # 剪断聚合关系词及其后内容
    for verb in ("连接前", "连接所有", "通过消息", "异步通知", "同步调用"):
        if verb in label:
            label = label.split(verb, 1)[0].strip(" ：:，,。")
    # 强制上限：12 个中文字符
    return _short(label.strip(" ：:，,。"), 12)


def _split_stages(text: str) -> list[str]:
    expected = _expected_count(text)
    candidate = _sequence_clause(text)
    parts = [_clean_stage_label(p) for p in _ARROW_RE.split(candidate) if _clean_stage_label(p)]
    if len(parts) < 3 or (expected and len(parts) < expected):
        list_parts = [_clean_stage_label(p) for p in _LIST_RE.split(candidate) if _clean_stage_label(p)]
        if len(list_parts) > len(parts):
            parts = list_parts
    noise = {
        "箭头连接",
        "用箭头连接",
        "箭头",
        "连线",
        "每个步骤用方框表示",
        "每步一个框",
        "方框表示",
    }
    out: list[str] = []
    for part in parts:
        if not part or len(part) <= 1 or part in noise or part.startswith("期望"):
            continue
        if re.fullmatch(r"(?:共)?\s*(?:\d+|[一二两三四五六七八九十])?\s*个?(?:步骤|阶段|环节|节点|模块)", part):
            continue
        if part not in out:
            out.append(part)
        if len(out) >= 14:
            break
    return out


def _rule_stages(text: str) -> list[dict[str, str]]:
    branched = _rule_parallel_feedback(text)
    if branched:
        return branched
    parts = _split_stages(text)
    stages = []
    for part in parts:
        stages.append({"id": f"s{len(stages)}", "label": part, "kind": _stage_kind(part)})
        if len(stages) >= 14:
            break
    return stages


def _rule_parallel_feedback(text: str) -> list[dict[str, str]] | None:
    return infer_grammar_stages_from_text(text)


def _normalize_stages(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    stages: list[dict[str, str]] = []
    for i, item in enumerate(raw[:14]):
        if isinstance(item, str):
            label = _short(item, 22)
            kind = _stage_kind(label)
            sid = f"s{i}"
            level = i
            column = 0
        elif isinstance(item, dict):
            label = _short(item.get("label") or item.get("name") or item.get("stage"), 22)
            kind = str(item.get("kind") or _stage_kind(label)).strip() or "step"
            sid = str(item.get("id") or f"s{i}").strip()
            try:
                level = int(item.get("level", i))
            except (TypeError, ValueError):
                level = i
            try:
                column = int(item.get("column", 0))
            except (TypeError, ValueError):
                column = 0
        else:
            continue
        if label:
            stages.append({"id": sid, "label": label, "kind": kind, "level": level, "column": column})
    return stages


def _normalize_edges(raw: Any, valid_ids: set[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw[:24]:
        if not isinstance(item, dict):
            continue
        src = str(item.get("from") or item.get("source") or "").strip()
        dst = str(item.get("to") or item.get("target") or "").strip()
        label = _short(item.get("label") or "", 12)
        if src in valid_ids and dst in valid_ids and src != dst:
            edge = {"from": src, "to": dst, "label": label}
            if edge not in out:
                out.append(edge)
    return out


def _to_graph(title: str, stages: list[dict[str, str]], edges: list[dict[str, str]], feedback: list[dict[str, str]] | None = None) -> dict[str, Any]:
    if not edges:
        edges = build_default_flow_edges(stages, feedback)
    edges = edges + [edge for edge in (feedback or []) if edge not in edges]
    shape_by_kind = {"decision": "diamond", "output": "rounded", "parallel": "box", "step": "rounded"}
    nodes = [
        {
            "id": stage["id"],
            "label": stage["label"],
            "shape": shape_by_kind.get(stage.get("kind", "step"), "rounded"),
            "level": int(stage.get("level", i)),
            "column": int(stage.get("column", 0)),
        }
        for i, stage in enumerate(stages)
    ]
    branched = any(stage.get("kind") in {"parallel", "decision"} for stage in stages) or bool(feedback)
    return {
        "diagram_subtype": "process_flow",
        "layout": "TB",
        "title": title,
        "structure_summary": f"{len(stages)} 个流程步骤",
        "stages": stages,
        "feedback": feedback or [],
        "nodes": nodes,
        "edges": edges,
    }


def parse_pipeline(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    if llm_available(ctx):
        data = call_llm_json(ctx, _PROMPT)
        if isinstance(data, dict):
            stages = _normalize_stages(data.get("stages"))
            ids = {s["id"] for s in stages}
            if stages:
                edges = _normalize_edges(data.get("edges"), ids)
                feedback = _normalize_edges(data.get("feedback"), ids)
                return ParsedDiagram(
                    _to_graph(_title(intent, data.get("title") or ctx.normalized_input), stages, edges, feedback),
                    "llm_pipeline",
                )
        return ParsedDiagram({"title": _title(intent, ctx.normalized_input)}, "llm_pipeline_failed")
    stages = _rule_stages(ctx.normalized_input)
    if not stages:
        stages = [
            {"id": "s0", "label": "输入", "kind": "step"},
            {"id": "s1", "label": "处理", "kind": "step"},
            {"id": "s2", "label": "输出", "kind": "output"},
        ]
    return ParsedDiagram(_to_graph(_title(intent, ctx.normalized_input), stages, []), "rules_pipeline")
