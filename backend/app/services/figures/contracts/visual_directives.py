"""Open-input visual intent extraction for structured figures.

The directive layer is not a template catalog.  It is a small set of reusable
visual intents that sit between semantic type detection and renderer profiles:
layout, edge treatment, visual encoding, readability, complexity policy, and a
few domain-neutral notation cues.  Keyword matching is only a deterministic
fallback for offline mode; when LLM visual briefs provide structured hints they
are merged into the same contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

Directive = dict[str, Any]

_NEGATION_RE = re.compile(r"(?:不|不要|无需|不用|禁止|避免|别|非|not|without)\s*$", re.I)

_ALIASES = {
    # Previous prototype ids, kept as compatibility shims for old traces/tests.
    "parallel_split_join": "layout.parallel",
    "feedback_loop": "edge.feedback",
    "decision_diamond": "node.decision_shape",
    "branch_labels": "edge.branch_label",
    "vertical_layers": "layout.layers",
    "two_column_shared_node": "layout.columns",
    "async_queue_semantics": "edge.async",
    "labeled_edges": "edge.label",
    "tree_hierarchy": "layout.tree",
    "symmetric_tree": "layout.symmetry",
    "timeline_axis": "layout.timeline",
    "alternating_timeline_labels": "label.alternate",
    "comparison_axes": "comparison.axis",
    "comparison_color_encoding": "encoding.color_scale",
    "bar_or_radar_comparison": "comparison.quantitative_form",
    "qkv_triplet": "semantic.qkv",
    "matrix_notation": "notation.matrix",
    "encoder_decoder_columns": "layout.encoder_decoder",
    "stacked_layers": "layout.stack",
    "bidirectional_color_arrows": "edge.bidirectional",
    "radial_center_satellites": "layout.radial",
    "relationship_edge_labels": "edge.relationship_label",
    "mixed_language_wrapping": "readability.mixed_text",
    "overflow_simplification": "complexity.summarize",
    "numeric_not_chart_guard": "routing.numeric_attribute",
}


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    patterns: tuple[str, ...]
    scope: tuple[str, ...] = ("*",)
    confidence: float = 0.72
    strength: str = "hard"


_RULES: tuple[Rule, ...] = (
    Rule("layout.parallel", "layout", (r"并行|parallel|split|分支.*汇合|汇合",), ("process_flow", "flowchart", "mechanism_diagram")),
    Rule("edge.feedback", "edge", (r"回路|循环|返回|反馈|重试|不达标|loop|feedback",), ("*",)),
    Rule("node.decision_shape", "node_shape", (r"判断|决策|是否|若.+则|if .+ then",), ("process_flow", "decision_tree", "flowchart")),
    Rule("edge.branch_label", "edge_label", (r"是[\\/／]否|是→|否→|箭头上|分支标签|branch label|yes|no",), ("process_flow", "decision_tree", "flowchart")),
    Rule("layout.layers", "layout", (r"三层|多层|顶层|中间层|底层|垂直排列|层间距|layer",), ("system_architecture", "mechanism_diagram")),
    Rule("layout.columns", "layout", (r"两列|双栏|左右|左侧|右侧|两侧|并排|side[- ]?by[- ]?side",), ("system_architecture", "comparison_matrix", "mechanism_diagram", "infographic")),
    Rule("layout.shared_resource", "layout", (r"共享|共用|公共|shared|central|居中",), ("system_architecture", "knowledge_graph")),
    Rule("edge.async", "edge", (r"异步|消息队列|队列|事件总线|queue|async|message bus",), ("system_architecture", "process_flow")),
    Rule("edge.label", "edge_label", (r"箭头标注|箭头有标签|标明|标注.+流向|连线标注|边标签|每条连线|relationship label",), ("*",)),
    Rule("layout.tree", "layout", (r"树形|树状|三级树|二级树|两级|三级|根节点|叶节点|分类",), ("taxonomy_map", "decision_tree")),
    Rule("layout.symmetry", "layout", (r"对称|三叉树|二叉树|均匀分布|同层|same level|balanced",), ("decision_tree", "taxonomy_map")),
    Rule("layout.timeline", "layout", (r"时间线|时间轴|里程碑|从左到右|横向排列|roadmap|timeline|q[1-4]",), ("timeline_roadmap", "process_flow")),
    Rule("label.alternate", "label_placement", (r"上下交替|交替.*标签|alternate",), ("timeline_roadmap",)),
    Rule("comparison.axis", "layout", (r"对比维度|维度[:：包括]|维度标签|每行对比|表格|矩阵|两列|三列",), ("comparison_matrix", "infographic")),
    Rule("encoding.color_scale", "visual_encoding", (r"深浅颜色|颜色区分|不同颜色|不同色块|色块|优劣|高低|color[- ]?cod",), ("comparison_matrix", "mechanism_diagram", "infographic", "process_flow")),
    Rule("comparison.quantitative_form", "layout", (r"横向条形|并行条形|雷达图|radar|bar chart|bar",), ("comparison_matrix",)),
    Rule("semantic.qkv", "semantic_role", (r"q[、,/／\\s]*k[、,/／\\s]*v|query.+key.+value",), ("mechanism_diagram",)),
    Rule("notation.matrix", "notation", (r"矩阵|权重矩阵|注意力权重|张量|matrix|tensor",), ("mechanism_diagram", "attention_matrix")),
    Rule("layout.encoder_decoder", "layout", (r"编码器.+解码器|encoder.+decoder|交叉注意力|cross attention",), ("mechanism_diagram", "system_architecture")),
    Rule("layout.stack", "layout", (r"n次堆叠|层叠|堆叠|stack",), ("mechanism_diagram", "system_architecture")),
    Rule("edge.bidirectional", "edge", (r"双向箭头|前向传播.+反向传播|反向传播|forward.+backward|bidirectional",), ("mechanism_diagram", "process_flow")),
    Rule("layout.radial", "layout", (r"辐射状|辐射布局|中心节点.+周围|中心.+连接|radial|hub[- ]and[- ]spoke",), ("concept_diagram", "knowledge_graph")),
    Rule("edge.relationship_label", "edge_label", (r"关系类型|关系标签|边标签|每条连线.+标注|predicate",), ("knowledge_graph", "concept_diagram")),
    Rule("readability.mixed_text", "readability", (r"中英混合|中英文|混排|mixed.+language|不换行溢出",), ("*",), confidence=0.68),
    Rule("complexity.summarize", "complexity_policy", (r"节点数过多|超长|截断|简化|拆成|强行塞进|too many",), ("*",), confidence=0.68),
    Rule("routing.numeric_attribute", "routing_guard", (r"不是坐标数据|不是数据图|不是图表数据|批大小不是|数值只是|numeric.+attribute",), ("*",), confidence=0.78),
    Rule("layout.card_grid", "layout", (r"信息图|信息块|模块排布|卡片|网格|grid|cards",), ("infographic", "chapter_summary")),
    Rule("encoding.iconic", "visual_encoding", (r"图标化|图标|icon",), ("infographic", "chapter_summary")),
    Rule("encoding.palette", "visual_encoding", (r"配色|色调|蓝白灰|蓝色系|palette|theme color",), ("infographic", "scene_illustration", "comparison_matrix")),
)


def extract_visual_directives(
    text: str,
    *,
    diagram_type: str = "",
    visual_brief: dict[str, Any] | None = None,
    content_brief: dict[str, Any] | None = None,
) -> list[Directive]:
    """Return normalized visual directives with scoped evidence.

    The function uses three evidence sources, in descending authority:
    structured content fields, structured visual brief hints, and prompt text.
    Prompt text rules are scoped by diagram type and skip local negations such
    as "不要用颜色区分".
    """

    source = str(text or "")
    dtype = _canonical_type(diagram_type)
    vb = visual_brief or {}
    content = content_brief or {}
    directives: list[Directive] = []

    def add(
        did: str,
        category: str,
        *,
        source_name: str,
        evidence: str = "",
        span: tuple[int, int] | None = None,
        confidence: float = 0.8,
        strength: str = "hard",
        scope: Iterable[str] | None = None,
    ) -> None:
        canonical = canonical_directive_id(did)
        if any(d.get("id") == canonical for d in directives):
            return
        item: Directive = {
            "id": canonical,
            "category": category,
            "strength": strength,
            "confidence": round(float(confidence), 3),
            "scope": list(scope or ([dtype] if dtype else ["*"])),
            "source": source_name,
        }
        if evidence:
            item["evidence"] = evidence[:80]
        if span:
            item["evidence_span"] = {"start": span[0], "end": span[1]}
        aliases = [old for old, new in _ALIASES.items() if new == canonical]
        if aliases:
            item["aliases"] = aliases
        directives.append(item)

    _add_from_content(content, add)
    _add_from_visual_brief(vb, add)

    for rule in _RULES:
        if not _in_scope(dtype, rule.scope):
            continue
        found = _find_rule(source, rule)
        if not found:
            continue
        match_text, span = found
        add(
            rule.id,
            rule.category,
            source_name="prompt_text",
            evidence=match_text,
            span=span,
            confidence=rule.confidence,
            strength=rule.strength,
            scope=rule.scope,
        )

    if _looks_mixed_language(source) and "readability.mixed_text" not in visual_directive_ids(directives):
        add(
            "readability.mixed_text",
            "readability",
            source_name="text_heuristic",
            evidence="CJK+ASCII terms",
            confidence=0.7,
            scope=("*",),
        )
    if _looks_overloaded(source) and "complexity.summarize" not in visual_directive_ids(directives):
        add(
            "complexity.summarize",
            "complexity_policy",
            source_name="text_heuristic",
            evidence="long enumerated structure",
            confidence=0.72,
            scope=("*",),
        )

    # Soft grammar defaults: these are renderer preferences, not user commands.
    if dtype in {"concept_diagram", "concept_map"} and "layout.radial" not in visual_directive_ids(directives):
        add("layout.radial", "layout", source_name="subtype_default", evidence=dtype, confidence=0.45, strength="soft")
    if dtype in {"decision_tree", "decision"} and "layout.symmetry" not in visual_directive_ids(directives):
        add("layout.symmetry", "layout", source_name="subtype_default", evidence=dtype, confidence=0.45, strength="soft")
    if dtype in {"timeline_roadmap", "timeline"} and "layout.timeline" not in visual_directive_ids(directives):
        add("layout.timeline", "layout", source_name="subtype_default", evidence=dtype, confidence=0.45, strength="soft")
    if dtype in {"infographic", "chapter_summary"} and "layout.card_grid" not in visual_directive_ids(directives):
        add("layout.card_grid", "layout", source_name="subtype_default", evidence=dtype, confidence=0.45, strength="soft")

    return directives


def _add_from_content(content: dict[str, Any], add) -> None:
    if content.get("parallel_groups"):
        add("layout.parallel", "layout", source_name="content_brief", evidence="parallel_groups", confidence=0.92)
    if content.get("loops") or content.get("feedbacks"):
        add("edge.feedback", "edge", source_name="content_brief", evidence="loops/feedbacks", confidence=0.92)
    if content.get("decisions"):
        add("node.decision_shape", "node_shape", source_name="content_brief", evidence="decisions", confidence=0.9)
        add("edge.branch_label", "edge_label", source_name="content_brief", evidence="decisions", confidence=0.82)
    if content.get("containers") or content.get("layers"):
        add("layout.layers", "layout", source_name="content_brief", evidence="containers/layers", confidence=0.86)
    if content.get("shared_resources"):
        add("layout.shared_resource", "layout", source_name="content_brief", evidence="shared_resources", confidence=0.9)
    if content.get("relations") or content.get("interactions"):
        add("edge.label", "edge_label", source_name="content_brief", evidence="relations/interactions", confidence=0.72)
    if content.get("blocks") or content.get("key_points"):
        add("layout.card_grid", "layout", source_name="content_brief", evidence="blocks/key_points", confidence=0.82)


def _add_from_visual_brief(vb: dict[str, Any], add) -> None:
    layout = str(vb.get("layout_intent") or "").lower()
    reading = str(vb.get("reading_order") or "").lower()
    comparison = str(vb.get("comparison_format") or "").lower()
    if layout in {"dual_column", "left_right", "left_right_containers", "lr_architecture"}:
        add("layout.columns", "layout", source_name="visual_brief", evidence=layout, confidence=0.86)
    if layout in {"layered", "vertical_layers"}:
        add("layout.layers", "layout", source_name="visual_brief", evidence=layout, confidence=0.84)
    if layout == "radial" or reading == "radial":
        add("layout.radial", "layout", source_name="visual_brief", evidence=layout or reading, confidence=0.86)
    if reading in {"left_to_right", "lr"}:
        add("layout.timeline", "layout", source_name="visual_brief", evidence=reading, confidence=0.66, strength="soft")
    if comparison in {"matrix", "table"}:
        add("comparison.axis", "layout", source_name="visual_brief", evidence=comparison, confidence=0.86)
    if comparison in {"bar_horizontal", "bar", "radar"}:
        add("comparison.quantitative_form", "layout", source_name="visual_brief", evidence=comparison, confidence=0.86)


def _find_rule(source: str, rule: Rule) -> tuple[str, tuple[int, int]] | None:
    for pattern in rule.patterns:
        for match in re.finditer(pattern, source, flags=re.I):
            start, end = match.span()
            if _is_negated(source, start):
                continue
            return match.group(0), (start, end)
    return None


def _is_negated(source: str, match_start: int) -> bool:
    prefix = source[max(0, match_start - 10):match_start]
    return bool(_NEGATION_RE.search(prefix))


def _looks_mixed_language(source: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", source or "") and re.search(r"[A-Za-z][A-Za-z0-9_-]{2,}", source or ""))


def _looks_overloaded(source: str) -> bool:
    text = source or ""
    if len(text) >= 220:
        return True
    enumerators = len(re.findall(r"[、,，；;]|（[^）]{4,80}）|\([^)]{4,80}\)", text))
    return enumerators >= 12


def _canonical_type(value: str) -> str:
    try:
        from app.services.figures.intent.taxonomy import canonical_subtype

        return canonical_subtype(value)
    except Exception:
        return str(value or "").strip().lower()


def _in_scope(dtype: str, scope: tuple[str, ...]) -> bool:
    if "*" in scope or not dtype:
        return True
    return dtype in {_canonical_type(s) for s in scope}


def canonical_directive_id(value: str) -> str:
    raw = str(value or "").strip()
    return _ALIASES.get(raw, raw)


def merge_visual_directives(*directive_lists: list[Directive] | None) -> list[Directive]:
    """Merge directive lists by canonical id while preserving first-seen order."""

    merged: list[Directive] = []
    seen: set[str] = set()
    for directives in directive_lists:
        for item in directives or []:
            if not isinstance(item, dict):
                continue
            did = canonical_directive_id(str(item.get("id") or ""))
            if not did or did in seen:
                continue
            seen.add(did)
            copied = dict(item)
            copied["id"] = did
            if "confidence" not in copied:
                copied["confidence"] = 0.7
            if "source" not in copied:
                copied["source"] = "external"
            merged.append(copied)
    return merged


def visual_directive_ids(value: Any) -> list[str]:
    directives = value if isinstance(value, list) else []
    ids: list[str] = []
    for directive in directives:
        if not isinstance(directive, dict):
            continue
        did = canonical_directive_id(str(directive.get("id") or ""))
        if did and did not in ids:
            ids.append(did)
    return ids


def mandatory_semantics_for_directives(directives: list[Directive] | None) -> list[str]:
    out: list[str] = []
    for directive in directives or []:
        if not isinstance(directive, dict):
            continue
        if str(directive.get("strength") or "hard") != "hard":
            continue
        did = canonical_directive_id(str(directive.get("id") or "")).strip()
        if did:
            out.append(f"directive:{did}")
    return list(dict.fromkeys(out))
