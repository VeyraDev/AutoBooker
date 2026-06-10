"""Visual Brief LLM 抽取。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.brief.context import build_context, format_intent_result
from app.services.figures.brief.schema import VisualBrief
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import PipelineContext
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


def extract_visual_brief(
    ctx: PipelineContext,
    understanding: dict[str, Any],
) -> VisualBrief:
    model = (ctx.model or settings.intent_model).strip()
    if ctx.use_llm and model and ctx.normalized_input.strip():
        data = _call_visual_brief_llm(ctx, understanding, model)
        if data:
            return VisualBrief.from_dict(data)
    return _minimal_brief(ctx, understanding)


def repair_visual_brief(
    ctx: PipelineContext,
    brief: VisualBrief,
    errors: list[str],
) -> VisualBrief | None:
    model = (ctx.model or settings.intent_model).strip()
    if not ctx.use_llm or not model or not errors:
        return None
    try:
        prompt = format_prompt(
            "brief_repair",
            text=ctx.normalized_input[:3500],
            broken_brief=json.dumps(brief.to_dict(), ensure_ascii=False)[:6000],
            errors="\n".join(errors[:12]),
        )
    except OSError:
        return None
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=2400,
            temperature=0.0,
        )
        data = parse_llm_json(out)
    except Exception as e:
        logger.warning("brief repair failed: %s", e)
        return None
    return VisualBrief.from_dict(data) if isinstance(data, dict) else None


def _call_visual_brief_llm(
    ctx: PipelineContext,
    understanding: dict[str, Any],
    model: str,
) -> dict[str, Any] | None:
    try:
        prompt = format_prompt(
            "visual_brief",
            text=ctx.normalized_input[:3500],
            intent_result=format_intent_result(understanding),
            context=build_context(ctx),
        )
    except OSError:
        return None
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=2800,
            temperature=0.0,
        )
        data = parse_llm_json(out)
    except Exception as e:
        logger.warning("visual brief LLM failed: %s", e)
        return None
    return data if isinstance(data, dict) else None


def _minimal_brief(ctx: PipelineContext, understanding: dict[str, Any]) -> VisualBrief:
    from app.services.figures.intent.taxonomy import canonical_subtype

    candidates = understanding.get("diagram_candidates") or understanding.get("candidate_diagrams") or []
    dtype = ""
    inferred = _infer_diagram_type_from_text(ctx.normalized_input)
    if ctx.subtype_hint:
        dtype = canonical_subtype(ctx.subtype_hint)
    elif inferred != "process_flow":
        dtype = inferred
    elif candidates and isinstance(candidates[0], dict):
        dtype = str(candidates[0].get("type") or "")
    if not dtype:
        dtype = inferred or "process_flow"
    title = str(understanding.get("title") or ctx.normalized_input[:24] or "示意图")
    content = _minimal_content_brief(dtype, ctx.normalized_input, title)
    return VisualBrief(
        diagram_type=dtype or "process_flow",
        title=title,
        content_brief=content,
        visual_brief={"density": "medium", "reading_order": "top_to_bottom", "style_intent": "modern_saas"},
    )


def _infer_diagram_type_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ("泳道", "swimlane", "lane")):
        return "swimlane"
    if any(k in t for k in ("对比", "比较", "vs", "优劣")):
        return "comparison_matrix"
    if any(k in t for k in ("架构", "微服务", "rag", "部署")):
        return "system_architecture"
    if any(k in t for k in ("时间线", "里程碑", "roadmap")):
        return "timeline_roadmap"
    if any(k in t for k in ("信息图", "信息块", "章节总结", "核心要点", "图标化")):
        return "infographic"
    if any(k in t for k in ("分类", "思维导图", "taxonomy", "层级")):
        return "taxonomy_map"
    if any(k in t for k in ("机制", "原理", "注意力", "transformer")):
        return "mechanism_diagram"
    return "process_flow"


def _minimal_content_brief(dtype: str, text: str, title: str) -> dict[str, Any]:
    import re

    from app.services.figures.intent.taxonomy import canonical_subtype as _canon

    st = _canon(dtype)
    steps = [
        {"label": p.strip()}
        for p in re.split(r"→|->|、|，|,|；|;", text)
        if p.strip() and len(p.strip()) <= 48
    ][:16]
    if st in {"timeline_roadmap", "timeline"}:
        return {"events": _extract_timeline_events(text) or [{"time": "", "label": title[:32]}]}
    if st in {"taxonomy_map", "mindmap", "org_chart"}:
        return _extract_taxonomy_content(text, title)
    if st in {"concept_diagram", "knowledge_graph"}:
        return _extract_relationship_content(text, title, network=(st == "knowledge_graph"))
    if st in {"decision_tree", "decision_flow"}:
        return _extract_decision_content(text, title)
    if st == "swot":
        return _extract_swot_content(text)
    if st == "attention_matrix":
        return _extract_attention_content(text, title)
    if st == "swimlane":
        lanes = re.findall(r"(\w+)\s*lane", text, flags=re.I)
        if not lanes:
            lanes = _extract_lane_labels(text) or ["用户", "系统", "后台"]
        return {
            "lanes": [
                {"label": lane, "items": steps[i::max(1, len(lanes))]}
                for i, lane in enumerate(lanes)
            ],
            "main_flow": steps or _extract_steps_from_sentence(text),
        }
    if st in {"comparison_matrix", "comparison"}:
        from app.services.figures.contracts.comparison_fill import fill_comparison_cells, infer_comparison_format

        subjects = re.findall(
            r"(LoRA|vLLM|TGI|DeepSpeed|全量微调|提示工程|LangChain|Hermes|React|FastAPI|PostgreSQL|[\u4e00-\u9fff]{2,8})",
            text,
        )
        subjects = list(dict.fromkeys(subjects))[:6] or ["方案A", "方案B"]
        dims = re.findall(r"(显存需求|训练速度|效果上限|适用场景|吞吐量|延迟|易用性|社区活跃度|成本|速度|复杂度|效果)", text)
        dims = list(dict.fromkeys(dims))[:8] or ["维度1", "维度2"]
        fmt = infer_comparison_format(text, {})
        base = {
            "subjects": subjects,
            "dimensions": [{"name": d} for d in dims],
            "comparison_goal": "summarize_tradeoffs" if len(subjects) == 2 else "compare",
            "comparison_format": fmt or ("pros_cons" if len(subjects) == 2 else "matrix"),
        }
        return fill_comparison_cells(base, source_text=text)
    if st in {"infographic", "chapter_summary"}:
        labels = [s["label"] for s in steps]
        if not labels:
            labels = _split_infographic_labels(text)
        return {"blocks": [{"label": lb, "items": []} for lb in labels[:6]] or [{"label": "要点", "items": []}]}
    if st in {"system_architecture", "shared_architecture"}:
        modules = [s["label"] for s in steps] or [title[:24]]
        interactions: list[dict[str, str]] = []
        gw = next((m for m in modules if any(k in m for k in ("网关", "Gateway", "API网关"))), "")
        if gw:
            interactions = [{"from": gw, "to": m, "label": "请求转发"} for m in modules if m != gw]
        elif len(modules) == 3:
            interactions = [
                {"from": modules[0], "to": modules[1], "label": "HTTP请求"},
                {"from": modules[1], "to": modules[0], "label": "HTTP响应"},
                {"from": modules[1], "to": modules[2], "label": "SQL"},
            ]
        return {"components": modules, "interactions": interactions, "architecture_pattern": "layered"}
    if steps:
        return {"main_flow": steps}
    return {"main_flow": [{"label": title[:32]}]}


def _split_infographic_labels(text: str) -> list[str]:
    import re

    cleaned = re.sub(r"[\"“”]", "", text or "")
    m = re.search(r"(?:展示|包含|包括|核心要点|关键概念)[:：]\s*([^。；;]+)", cleaned)
    raw = m.group(1) if m else cleaned
    raw = re.split(r"(?:，|,|；|;)?\s*(?:用|以|通过)?(?:图标|卡片|分栏|展示|呈现|白底|配色)", raw, 1)[0]
    parts = re.split(r"[、,，/]|和|与", raw)
    out: list[str] = []
    for part in parts:
        label = re.sub(r"\s+", " ", part.strip())[:18]
        if label and label not in out:
            out.append(label)
    return out[:6]


def _split_labels(raw: str, *, limit: int = 12) -> list[str]:
    import re

    cleaned = re.sub(r"[。；;]", "，", raw or "")
    parts = re.split(r"[、,，/]|以及|和|与|及", cleaned)
    out: list[str] = []
    for part in parts:
        label = re.sub(r"^(包括|包含|分别是|有|为|是|则|选择|连接|关联)\s*", "", part.strip())
        label = re.sub(r"\s+", " ", label).strip(" ：:，,。；;")
        if label and len(label) <= 24 and label not in out:
            out.append(label)
    return out[:limit]


def _extract_timeline_events(text: str) -> list[dict[str, str]]:
    import re

    events: list[dict[str, str]] = []
    pattern = re.compile(r"((?:20\d{2}\s*)?Q[1-4]|20\d{2}年?\s*(?:上半年|下半年|第?[一二三四1-4]季度)?|第[一二三四五六七八九十]+阶段)\s*([^，,。；;]+)")
    for m in pattern.finditer(text or ""):
        time_val = re.sub(r"\s+", " ", m.group(1)).strip()
        label = m.group(2).strip(" ：:，,。；;")
        label = re.sub(r"^(完成|发布|接入|做|进行)", "", label).strip() or m.group(2).strip()
        if time_val and label:
            events.append({"time": time_val, "label": label[:32]})
    if events:
        return events[:12]
    chunks = _split_labels(text, limit=8)
    return [{"time": f"阶段{i + 1}", "label": label[:32]} for i, label in enumerate(chunks)]


def _extract_taxonomy_content(text: str, title: str) -> dict[str, object]:
    import re

    root = title[:24] or "分类"
    m = re.search(r"(?:根节点|中心|根)\s*(?:是|为)[:：]?\s*([^，,。；;]+)", text or "")
    if m:
        root = m.group(1).strip(" ：:，,。；;")[:24]
    cats_raw = ""
    m = re.search(r"(?:一级分类|分类|包括|包含)[^：:]*[:：]?\s*([^。；;]+)", text or "")
    if m:
        cats_raw = m.group(1)
    categories = _split_labels(cats_raw or text, limit=8)
    categories = [c for c in categories if c and c != root][:8] or ["类别A", "类别B"]
    add_examples = bool(re.search(r"每类.*(?:两个|2个|典型子类|子类)", text or ""))
    children = []
    for cat in categories:
        node: dict[str, object] = {"label": cat, "children": []}
        if add_examples:
            node["children"] = [{"label": f"{cat}示例1"}, {"label": f"{cat}示例2"}]
        children.append(node)
    return {"root": root, "children": children}


def _extract_relationship_content(text: str, title: str, *, network: bool = False) -> dict[str, object]:
    import re

    center = title[:24] or ("知识图谱" if network else "中心概念")
    m = re.search(r"(?:中心|中心是|根节点|主题)\s*(?:是|为)?[:：]?\s*([^，,。；;]+)", text or "")
    if m:
        center = m.group(1).strip(" ：:，,。；;")[:24]
    elif network:
        m = re.search(r"([\u4e00-\u9fffA-Za-z0-9_ -]{2,16})(?:连接|关联|包括)", text or "")
        if m:
            center = m.group(1).strip(" ：:，,。；;")[:24]

    raw = ""
    m = re.search(r"(?:周围关联|周围连接|关联|连接|包括|包含)[:：]?\s*([^。；;]+)", text or "")
    if m:
        raw = m.group(1)
    concepts = [c for c in _split_labels(raw or text, limit=10) if c != center]
    concepts = concepts[:10] or ["概念A", "概念B", "概念C"]
    relations = [{"from": center, "to": c, "label": "关联"} for c in concepts]

    verbs = "调用|产生|更新|影响|生成|访问|连接|依赖|包含|约束|设定"
    for m in re.finditer(rf"([^，,。；;]{{1,16}}?)({verbs})([^，,。；;]{{1,16}})", text or ""):
        src = m.group(1).strip(" ：:，,。；;")
        verb = m.group(2)
        tgt = m.group(3).strip(" ：:，,。；;")
        if src and tgt and src != tgt:
            relations.append({"from": src[:24], "to": tgt[:24], "label": verb})
            for label in (src[:24], tgt[:24]):
                if label not in concepts and label != center:
                    concepts.append(label)
    return {"center": center, "concepts": concepts[:12], "relations": relations[:18]}


def _extract_decision_content(text: str, title: str) -> dict[str, object]:
    import re

    conditions = []
    for m in re.finditer(r"(?:先)?判断([^；;。]+?)(?=；|;|。|，|,|$)", text or ""):
        cond = m.group(1).strip(" 是否：:，,。；;")
        if cond:
            conditions.append("是否" + cond if not cond.startswith("是否") else cond)
    outcomes = []
    for m in re.finditer(r"(?:选择|则选择)([^，,。；;]+)", text or ""):
        val = m.group(1).strip(" ：:，,。；;")
        if val and val not in outcomes:
            outcomes.append(val[:24])
    root = conditions[0] if conditions else title[:32] or "是否满足条件"
    if not outcomes:
        outcomes = ["方案A", "方案B"]
    decisions: list[dict[str, object]] = []
    if len(conditions) <= 1:
        decisions.append({
            "condition": root,
            "branches": [
                {"label": "是", "target": outcomes[0]},
                {"label": "否", "target": outcomes[1] if len(outcomes) > 1 else outcomes[0]},
            ],
        })
    else:
        decisions.append({
            "condition": root,
            "branches": [
                {"label": "是", "target": outcomes[0]},
                {"label": "否", "target": conditions[1]},
            ],
        })
        decisions.append({
            "condition": conditions[1],
            "branches": [
                {"label": "是", "target": outcomes[1] if len(outcomes) > 1 else outcomes[0]},
                {"label": "否", "target": outcomes[2] if len(outcomes) > 2 else outcomes[-1]},
            ],
        })
    return {
        "root_decision": root,
        "decisions": decisions,
        "outcomes": [{"label": o} for o in outcomes],
    }


def _extract_swot_content(text: str) -> dict[str, list[str]]:
    import re

    keys = {
        "strengths": "优势",
        "weaknesses": "劣势",
        "opportunities": "机会",
        "threats": "威胁",
    }
    out: dict[str, list[str]] = {}
    for key, label in keys.items():
        m = re.search(rf"{label}(?:包括|有|为)?([^。；;]+)", text or "")
        items = _split_labels(m.group(1) if m else "", limit=4)
        out[key] = items or [f"{label}项"]
    return out


def _extract_attention_content(text: str, title: str) -> dict[str, object]:
    import re

    size = 6
    m = re.search(r"(\d+)\s*[xX×]\s*(\d+)", text or "")
    if m:
        size = max(2, min(24, int(m.group(1))))
    tokens = []
    m = re.search(r"tokens?\s*(?:为|是|包括)?\s*([^。；;]+)", text or "", flags=re.I)
    if m:
        tokens = _split_labels(m.group(1), limit=size)
    tokens = tokens or [f"T{i + 1}" for i in range(size)]
    cells = []
    for i, src in enumerate(tokens):
        for j, tgt in enumerate(tokens):
            weight = 0.25
            if i == j:
                weight = 0.6
            if f"{src}到{tgt}" in (text or "") or f"{src}->{tgt}" in (text or ""):
                weight = 0.9
            cells.append({"row": src, "column": tgt, "value": weight})
    return {"title": title or "注意力矩阵", "tokens": tokens, "size": len(tokens), "cells": cells}


def _extract_lane_labels(text: str) -> list[str]:
    import re

    m = re.search(r"泳道(?:包括|有|为)?([^。；;]+)", text or "")
    return _split_labels(m.group(1) if m else "", limit=8)


def _extract_steps_from_sentence(text: str) -> list[dict[str, str]]:
    labels = _split_labels(text, limit=12)
    return [{"label": label} for label in labels]
