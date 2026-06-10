"""Semantic Native IR 审查（无关键词规则，结构一致性检查）。"""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import PipelineContext
from app.services.figures.semantic.native_bridge import expected_native_type
from app.services.figures.semantic.schema import SemanticIR
from app.utils.json_llm import parse_llm_json

_LAYOUT_NOISE = re.compile(r"左侧|右侧|箭头连接|共\d+个|前\d+个|用箭头|布局|版式")
_STRUCTURE_IN_LABEL = re.compile(r"下(?:面)?(?:有|为|分)")


def run_semantic_critic(
    ir: SemanticIR,
    source_text: str,
    *,
    ctx: PipelineContext | None = None,
    diagram_type: str = "",
    diagram_subtype: str = "",
) -> dict[str, Any]:
    """返回 {passed, issues, severity, source}。"""
    subtype = canonical_subtype(diagram_subtype)
    issues = _rule_based_critic(ir, source_text, subtype=subtype)
    llm_issues = _llm_critic(
        ir, source_text, ctx=ctx, diagram_type=diagram_type, diagram_subtype=subtype,
    ) if ctx and ctx.use_llm else []
    merged = list(dict.fromkeys(issues + llm_issues))
    severity = "error" if merged else "none"
    if merged and not any(i.startswith("missing_") for i in merged):
        severity = "warning" if len(merged) <= 2 else "error"
    return {
        "passed": True,
        "issues": merged,
        "warnings": merged,
        "severity": severity if merged else "none",
        "source": "rule+llm" if llm_issues else "rule",
    }


def _rule_based_critic(ir: SemanticIR, text: str, *, subtype: str = "") -> list[str]:
    issues: list[str] = []
    native = ir.native_structure or {}
    ntype = ir.native_type() or (ir.diagram_type or "").lower()
    expected = expected_native_type(subtype) if subtype else ""

    if not native and len(ir.objects) < 2:
        issues.append("missing_native_structure")
        return issues

    if ntype in {"comparison_matrix", "comparison"}:
        subjects = native.get("subjects") or native.get("columns") or []
        dims = native.get("dimensions") or []
        if not subjects or not dims:
            issues.append("comparison_missing_subjects_or_dimensions")
        if native.get("steps") or (len(ir.objects) >= 3 and ir.relations and not subjects):
            issues.append("comparison_flattened_to_flow")

    elif ntype in {"timeline", "timeline_roadmap"}:
        milestones = native.get("milestones") or native.get("events") or []
        if len(milestones) < 2:
            issues.append("timeline_missing_milestones")
        elif not any(isinstance(m, dict) and (m.get("time") or m.get("label")) for m in milestones):
            issues.append("timeline_missing_time_labels")

    elif ntype in {"taxonomy", "taxonomy_map"}:
        children = native.get("children") or []
        if not native.get("root") and not ir.title:
            issues.append("taxonomy_missing_root")
        if len(children) < 1:
            issues.append("taxonomy_missing_children")
        elif _taxonomy_flattened(children):
            issues.append("taxonomy_flattened_to_first_branch")

    elif ntype in {"shared_architecture", "architecture", "system_architecture"}:
        comps = native.get("components") or []
        if not comps and not native.get("groups"):
            issues.append("architecture_missing_components")

    elif ntype in {"process_flow", "flowchart", "pipeline"}:
        issues.extend(_critic_process_flow(native, text))

    elif ntype in {"mechanism", "mechanism_diagram"}:
        if not native.get("steps") and not (native.get("inputs") and native.get("outputs")):
            issues.append("mechanism_missing_structure")

    elif ntype == "infographic":
        blocks = native.get("blocks") or []
        if not blocks:
            issues.append("infographic_missing_blocks")
        elif len(blocks) < 2 and not any(
            isinstance(b, dict) and (b.get("items") or []) for b in blocks
        ):
            issues.append("infographic_sparse_blocks")

    elif ntype in {"decision_tree", "decision_flow"}:
        if not native.get("root") and not native.get("branches"):
            issues.append("decision_tree_missing_structure")

    elif ntype == "chart":
        if not native.get("labels") and not native.get("values"):
            issues.append("chart_missing_data")

    elif ntype == "concept":
        concepts = native.get("concepts") or []
        if len(concepts) < 2:
            issues.append("concept_missing_nodes")

    for key in ("subjects", "dimensions", "milestones", "steps", "components", "children"):
        for item in _flatten_labels(native.get(key)):
            if _LAYOUT_NOISE.search(item):
                issues.append(f"layout_noise_in_{key}")
            if _STRUCTURE_IN_LABEL.search(item):
                issues.append(f"structure_word_in_{key}")

    if "对比" in text and ntype in {"process_flow", "flowchart"} and "comparison" not in ntype:
        if not native.get("subjects"):
            issues.append("wrong_type_should_be_comparison")

    if ntype == "concept" and _PARALLEL_RE.search(text):
        issues.append("wrong_type_should_be_process_flow")

    if subtype == "mechanism_diagram" and ntype in {"process_flow", "flowchart"}:
        issues.append("wrong_type_mechanism_vs_flow")
    if subtype == "process_flow" and ntype in {"mechanism", "mechanism_diagram"}:
        issues.append("wrong_type_flow_vs_mechanism")
    if subtype == "infographic" and ntype in {"concept", "taxonomy"}:
        issues.append("wrong_type_should_be_infographic")
    if expected and ntype and expected != ntype and expected not in {ntype}:
        pair = (ntype, expected)
        ok_pairs = {
            ("flowchart", "process_flow"), ("process_flow", "flowchart"),
            ("architecture", "shared_architecture"), ("shared_architecture", "architecture"),
            ("comparison", "comparison_matrix"), ("comparison_matrix", "comparison"),
            ("timeline_roadmap", "timeline"), ("timeline", "timeline_roadmap"),
            ("taxonomy_map", "taxonomy"), ("taxonomy", "taxonomy_map"),
            ("concept_diagram", "concept"), ("concept", "concept_diagram"),
            ("mechanism_diagram", "mechanism"), ("mechanism", "mechanism_diagram"),
        }
        if pair not in ok_pairs:
            issues.append(f"native_type_mismatch:{ntype}_expected_{expected}")

    return issues


_PARALLEL_RE = re.compile(r"并行|两支|两个.{0,6}分支|分叉|汇合")


def _critic_process_flow(native: dict[str, Any], text: str) -> list[str]:
    from app.services.figures.semantic.flow_semantic import coerce_process_flow_native, flow_semantic_critic

    if native.get("steps") and not native.get("nodes"):
        issues = ["flow_legacy_steps_format"]
        issues.extend(flow_semantic_critic(coerce_process_flow_native(native, text), text))
        return list(dict.fromkeys(issues))
    return flow_semantic_critic(native, text)


def _taxonomy_flattened(children: list) -> bool:
    if len(children) < 2:
        return False
    counts = [len(c.get("children") or []) for c in children if isinstance(c, dict)]
    total = sum(counts)
    return total >= 3 and counts and counts[0] == total


def _flatten_labels(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                out.append(str(item.get("label") or item.get("name") or ""))
        return out
    return []


def _llm_critic(
    ir: SemanticIR,
    source_text: str,
    *,
    ctx: PipelineContext | None,
    diagram_type: str,
    diagram_subtype: str = "",
) -> list[str]:
    model = (ctx.model if ctx else "") or settings.intent_model
    if not model.strip():
        return []
    try:
        prompt = format_prompt(
            "semantic_critic",
            diagram_type=diagram_type or ir.diagram_type,
            diagram_subtype=diagram_subtype or ir.diagram_type,
            text=source_text[:3000],
            semantic_json=str(ir.to_dict())[:4000],
        )
    except OSError:
        return []
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model.strip(),
            max_tokens=800,
            temperature=0.0,
        )
        data = parse_llm_json(out)
    except Exception:
        return []
    if not isinstance(data, dict) or data.get("passed"):
        return []
    return [str(x) for x in (data.get("issues") or []) if str(x).strip()]
