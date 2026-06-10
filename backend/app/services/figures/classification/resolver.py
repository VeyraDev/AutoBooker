"""parsed_spec + intent → ClassificationRecord。"""

from __future__ import annotations

import re

from app.services.figure_render.renderer_rules import has_numeric_data_signal, style_profile_for_book
from app.services.figures.quality import initial_quality_report, intent_candidate_report
from app.services.figures.intent.taxonomy import (
    RENDERER_ILLUSTRATION,
    RENDERER_NEED_DATA,
    RENDERER_STRUCTURED_CHART,
    RENDERER_UPLOAD,
    SUBTYPE_TO_LEGACY_IMAGE_TYPE,
    canonical_subtype,
    resolve_renderer_key,
)
from app.services.figures.layout.policies import field_constraints_for_subtype, get_layout_policy
from app.services.figures.schemas.diagram import (
    ClassificationRecord,
    DiagramIntent,
    ParsedDiagram,
    PipelineContext,
    VisualPlan,
)

_LONG_PUNCT_RE = re.compile(r"[，,。；;：:、\n]")

_SUBTYPE_STYLE: dict[str, str] = {
    "process_flow": (
        "clean flowchart; rounded-rect nodes; node background #EEF3FD stroke #3B7DD8; "
        "LR layout for ≤5 nodes, TB for longer; 60px node gap; node width adapts to label; "
        "decision nodes use diamond shape with amber fill #FEF3C7 stroke #D97706; "
        "feedback/retry edges use dashed stroke; start/end nodes use pill shape gray fill"
    ),
    "business_workflow": (
        "process flowchart with swim-lanes; lane headers bold gray; "
        "step nodes rounded-rect steel-blue; hand-off arrows cross lane boundary; "
        "decision diamonds amber; terminal nodes pill-shaped"
    ),
    "system_architecture": (
        "layered architecture diagram; each layer a labeled rounded container band "
        "(入口层=blue-100, 服务层=teal-50, 基础设施层=slate-50); "
        "module cards inside layers: white card 1px border rounded-8 drop-shadow-xs; "
        "gateway/entry modules amber accent border; infra/queue modules slate; "
        "cross-layer arrows thin 1px; avoid fan-out spaghetti: group related connections"
    ),
    "microservice_architecture": (
        "microservice topology; services as rounded cards grouped by domain; "
        "message bus/queue shown as horizontal rail between service groups; "
        "sync calls solid arrow, async calls dashed arrow; "
        "API gateway prominent at top with distinct amber fill"
    ),
    "decision_tree": (
        "top-down decision tree; diamond nodes for yes/no decisions amber fill #FEF9C3; "
        "outcome leaf nodes rounded-rect teal fill #CCFBF1; "
        "edge labels: short (是/否/Y/N); 80px vertical gap between levels; "
        "root node larger; consistent node widths per level"
    ),
    "comparison_matrix": (
        "comparison table or 2-column card layout; "
        "one distinct color ramp per option (blue vs teal, or purple vs coral); "
        "bold header row with option name; attribute rows alternating white/gray-50; "
        "highlight winner cells with subtle green-100 background"
    ),
    "swot": (
        "2×2 SWOT quadrant; each quadrant distinct background "
        "(S=green-50, W=red-50, O=blue-50, T=amber-50); "
        "quadrant label bold in matching dark ramp color; "
        "bullet items inside each quadrant 12px; center diamond optional logo placeholder"
    ),
    "timeline_roadmap": (
        "horizontal timeline rail with milestone markers; "
        "rail line 2px gray-300; milestone circles filled blue-500 with white center dot; "
        "labels alternate above/below rail to avoid overlap; "
        "phase bands behind milestones for grouping; quarter/year markers on rail"
    ),
    "taxonomy_map": (
        "radial mind-map or indented tree; root node large centered purple fill; "
        "level-1 branches teal rounded-rect connected by curved paths; "
        "level-2 nodes smaller gray; leaf nodes smallest, text only; "
        "use curved bezier connectors not straight lines"
    ),
    "org_chart": (
        "top-down org chart; CEO/root at top center large blue card; "
        "direct reports row below connected by vertical lines; "
        "each node: name bold + role subtitle 12px; "
        "same-level nodes equal width; department groups optionally framed"
    ),
    "knowledge_graph": (
        "entity-relation network; entity nodes circles or rounded-rect by type; "
        "relation edges labeled with predicate; "
        "hub nodes larger; use force-directed-style manual spacing; "
        "color by entity type: person=purple, org=blue, concept=teal, event=amber"
    ),
    "infographic": (
        "2×N icon-text card grid; each card: icon top-center 32px + title bold 14px + "
        "1-line summary 12px; consistent card height 100px; "
        "cards use alternating light color backgrounds from a single ramp; "
        "section header above grid if multiple groups"
    ),
    "chart": (
        "data visualization chart; choose bar/line/pie by data shape; "
        "bars use single blue ramp with slight opacity variation; "
        "axis labels 11px gray; grid lines 0.5px gray-100; "
        "data labels on bars if ≤8 items; legend only if multiple series"
    ),
    "transformer": (
        "transformer architecture cross-section; encoder left, decoder right (or stacked); "
        "attention heads shown as small colored squares inside attention block; "
        "residual connections as curved bypass arrows; "
        "input embedding at bottom, output probabilities at top; "
        "layer norm and FFN blocks labeled clearly; warm blue palette"
    ),
    "rag": (
        "RAG pipeline or architecture hybrid; "
        "if pipeline (A→B→C flow): clean LR flowchart with document icon at retriever; "
        "if architecture (components): layered with vector store prominent bottom; "
        "retriever teal, LLM blue, vector store slate, user query amber; "
        "show both query path (solid) and retrieval path (dashed) if both present"
    ),
    "agent": (
        "agent loop diagram; perception-planning-action cycle shown as circular or spiral; "
        "tool nodes as small cards around agent core; "
        "memory module as persistent side panel; "
        "action arrows show feedback loop; warm purple for agent core"
    ),
    "attention_matrix": (
        "attention weight heatmap; tokens on both axes; "
        "cell fill: warm amber-red for high attention, cool blue-gray for low; "
        "token labels 11px on axes; causal mask shown as gray triangle if applicable; "
        "softmax row highlighted with subtle border"
    ),
    "concept_diagram": (
        "concept relationship map; central concept large rounded-rect blue; "
        "related concepts medium teal nodes; peripheral notes small gray; "
        "labeled edges 11px describing the relationship; "
        "radial or hierarchical layout based on concept count"
    ),
    "mechanism_diagram": (
        "mechanism explainer; input/output nodes at edges; "
        "internal process steps as sequential boxes; "
        "data transformation shown by arrow label changes; "
        "use icons where possible: gear for processing, funnel for filtering, "
        "lightning for activation; teal-blue palette"
    ),
    "scene_illustration": (
        "editorial scene illustration; atmospheric, human-centered; "
        "avoid diagram conventions (no boxes, no arrows, no labels); "
        "use storytelling composition: foreground character, background context; "
        "soft muted palette with one warm accent; photographic style optional"
    ),
}

_DEFAULT_STYLE = (
    "book interior diagram; unified blue-gray node fills; icon badges for semantic hints; "
    "generous 60px node spacing; 0.5px clean vector borders; "
    "title centered top; no decorative backgrounds"
)


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


def _shorten_title(raw: str, *, fallback: str = "示意图") -> str:
    """Keep figure titles short enough to be rendered inside book diagrams."""
    text = re.sub(r"\s+", " ", str(raw or "").strip())
    text = re.sub(r"^(图\s*\d+\s*[-–—]\s*\d+\s*[:：]\s*)", "", text)
    text = re.sub(r"^(请|生成|绘制|画一张|一张)", "", text).strip(" ：:，,。")
    if not text:
        return fallback
    first = _LONG_PUNCT_RE.split(text, 1)[0].strip(" ：:，,。")
    if first and _visual_len(first) <= 24:
        return first
    out = ""
    for ch in (first or text):
        if _visual_len(out + ch) > 24:
            break
        out += ch
    return out.strip(" ：:，,。") or fallback


def _structured_quality(parsed_spec: dict, subtype: str, renderer: str) -> tuple[list[str], list[str], str]:
    warnings: list[str] = []
    flags: list[str] = []
    st = canonical_subtype(subtype)
    policy = get_layout_policy(st)
    constraints = field_constraints_for_subtype(st)
    layout = str(parsed_spec.get("layout_strategy") or parsed_spec.get("layout") or "").upper()
    nodes = [n for n in (parsed_spec.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (parsed_spec.get("edges") or []) if isinstance(e, dict)]

    if renderer == RENDERER_ILLUSTRATION:
        return warnings, flags, "image_api"
    if st == "chart" or renderer == RENDERER_STRUCTURED_CHART:
        return warnings, flags, "chart"

    strategy = layout or (policy.strategies[0] if policy.strategies else policy.default_direction)

    if not renderer.startswith("structured."):
        return warnings, flags, strategy

    if st in {"chart"}:
        return warnings, flags, "chart"

    if not nodes and "nodes" in constraints["required_fields"]:
        flags.append("missing_nodes")
        warnings.append("结构化图缺少节点")
        return warnings, flags, strategy

    max_soft = int(constraints.get("max_nodes_soft") or 16)
    max_hard = int(constraints.get("max_nodes_hard") or 22)
    if len(nodes) > max_hard:
        flags.append("complex_graph")
        warnings.append("节点过多，建议分组或拆成多张图")
        strategy = "grouped"
    elif len(nodes) > max_soft:
        flags.append("dense_graph")
        warnings.append("节点偏多，将启用紧凑布局")

    for field in constraints["required_fields"]:
        if field in {"nodes", "edges"}:
            continue
        if not parsed_spec.get(field):
            flags.append(f"missing_{field}")
            warnings.append(f"缺少推荐字段 {field}")

    if st in {"process_flow", "business_workflow", "mechanism_diagram"}:
        if len(edges) < max(0, len(nodes) - 1):
            flags.append("edge_gap")
            warnings.append("流程/时间线边数量不足，渲染前会尝试补齐顺序连线")
        strategy = policy.strategies[0] if policy.strategies else "TB"
    elif st in {"timeline_roadmap", "timeline", "roadmap"}:
        if len(edges) < max(0, len(nodes) - 1):
            flags.append("edge_gap")
            warnings.append("时间线边数量不足，渲染前会尝试补齐顺序连线")
        strategy = "snake" if len(nodes) > 6 else "LR"
    if st in {"decision_tree", "decision_flow"} and len(edges) < max(0, len(nodes) - 1):
        flags.append("decision_edge_gap")
        warnings.append("决策树分支不完整，渲染前会尝试补齐父子连线")
        strategy = "TB_Decision"
    if parsed_spec.get("title") and _visual_len(str(parsed_spec.get("title"))) > 28:
        flags.append("long_title")
        warnings.append("图内标题过长，已压缩为短标题")
    return warnings, flags, strategy


def _semantic_labels(parsed_spec: dict) -> list[str]:
    labels: list[str] = []
    for node in parsed_spec.get("nodes") or []:
        if isinstance(node, dict) and node.get("label"):
            labels.append(str(node["label"]))
    for stage in parsed_spec.get("stages") or []:
        if isinstance(stage, dict) and stage.get("label"):
            labels.append(str(stage["label"]))
    for layer in parsed_spec.get("layers") or []:
        if isinstance(layer, dict):
            labels.extend(str(x) for x in (layer.get("modules") or []) if str(x).strip())
    labels.extend(str(x) for x in (parsed_spec.get("columns") or []) if str(x).strip())
    labels.extend(str(x) for x in (parsed_spec.get("dimensions") or []) if str(x).strip())
    for block in parsed_spec.get("blocks") or []:
        if isinstance(block, dict) and block.get("label"):
            labels.append(str(block["label"]))
    return labels


def _image_api_safe_for_structured(parsed_spec: dict, subtype: str) -> bool:
    mode = str(parsed_spec.get("render_mode") or "").strip().lower()
    if mode not in {"image_api", "illustration", "illustrative_image"}:
        return False
    if subtype in {"chart", "attention_matrix", "swot"}:
        return False
    labels = _semantic_labels(parsed_spec)
    if not labels or len(labels) > 8:
        return False
    return all(_visual_len(label) <= 10 for label in labels)


def _visual_requirements_for(subtype: str, renderer: str) -> list[str]:
    base = [
        "节点标签只保留语义短名，禁止版式说明文字",
        "节点间距充足，连线不穿过文字或节点",
    ]
    if renderer == RENDERER_ILLUSTRATION:
        return base + ["场景氛围优先，无文字标注框", "构图有前景/背景层次"]
    subtype_extras = {
        "process_flow": ["步骤节点等高等宽", "决策菱形与步骤矩形形状明确区分", "反馈边用虚线"],
        "system_architecture": ["层容器背景区分明显", "跨层箭头不交叉", "网关/入口节点用强调色"],
        "comparison_matrix": ["每列颜色独立", "表头加粗", "对比维度左对齐"],
        "infographic": ["每个信息块等高", "图标与文字对齐", "最多2×4格布局"],
        "timeline_roadmap": ["时间轴水平居中", "里程碑标签交错上下避免重叠", "阶段带状背景"],
        "decision_tree": ["根节点居顶居中", "同层节点等高", "叶节点用不同背景色标记结果"],
        "taxonomy_map": ["根节点最大", "子节点按层递减", "连线用曲线而非折线"],
        "chart": ["坐标轴标注清晰", "数据标签避免重叠", "单系列用单色渐变"],
        "rag": ["检索路径与生成路径颜色分离", "向量库图标明确", "查询节点置顶"],
    }
    return base + subtype_extras.get(subtype, ["统一配色主题", "节点形状语义化"])


def build_classification_record(
    ctx: PipelineContext,
    intent: DiagramIntent,
    parsed: ParsedDiagram,
    *,
    visual_plan: VisualPlan | None = None,
    dsl_json: dict | None = None,
    ir_bundle: dict | None = None,
) -> ClassificationRecord:
    subtype = canonical_subtype(intent.diagram_subtype)
    if subtype == "data_visualization":
        subtype = "chart"

    numeric = has_numeric_data_signal(ctx.normalized_input)
    if parsed.parsed_spec.get("values") or parsed.parsed_spec.get("series"):
        numeric = True

    renderer = resolve_renderer_key(subtype, has_numeric_data=numeric)
    if subtype == "chart":
        renderer = RENDERER_STRUCTURED_CHART
    if _image_api_safe_for_structured(parsed.parsed_spec, subtype) and subtype != "chart":
        renderer = RENDERER_ILLUSTRATION
        parsed.parsed_spec.setdefault("quality_flags", []).append("image_api_structured_visual")
        parsed.parsed_spec.setdefault("render_warnings", []).append("低文字结构视觉图允许使用 Image API，并保留结构化计划用于审查")
    # Only real scene illustrations go to Image API. Text-heavy information graphics should stay structured.
    if intent.diagram_family == "illustration" and subtype in {"scene_illustration", "case_scene", "future_scene", "human_ai_scene"}:
        renderer = RENDERER_ILLUSTRATION
    if subtype == "chart":
        renderer = RENDERER_STRUCTURED_CHART

    image_type = SUBTYPE_TO_LEGACY_IMAGE_TYPE.get(subtype, "concept_diagram")
    if renderer == RENDERER_ILLUSTRATION:
        image_type = "scene_illustration"

    parsed_title = str(parsed.parsed_spec.get("title") or "").strip()
    title_source = intent.title or parsed_title or ctx.chapter_title
    title = _shorten_title(title_source, fallback="示意图")
    if parsed.parsed_spec.get("title"):
        parsed.parsed_spec["title"] = _shorten_title(str(parsed.parsed_spec.get("title")), fallback=title)
    parsed.parsed_spec["diagram_subtype"] = subtype
    render_warnings, quality_flags, layout_strategy = _structured_quality(parsed.parsed_spec, subtype, renderer)
    render_warnings = list(dict.fromkeys(list(parsed.parsed_spec.get("render_warnings") or []) + render_warnings))
    quality_flags = list(dict.fromkeys(list(parsed.parsed_spec.get("quality_flags") or []) + quality_flags))
    intent_candidates = intent_candidate_report(ctx, intent)
    must_avoid = ["照片写实", "复杂背景", "营销海报风", "文字堆叠"]
    if renderer == RENDERER_ILLUSTRATION:
        must_avoid.extend(["可读文字", "复杂标签", "UI 截图伪造"])
    else:
        must_avoid.extend(["装饰性插画", "伪 3D", "过多颜色"])

    style = _SUBTYPE_STYLE.get(subtype, _DEFAULT_STYLE)
    if visual_plan and visual_plan.style:
        style = visual_plan.style

    ir = ir_bundle or {}
    semantic_ir = ir.get("semantic_ir") or ir.get("native_ir")
    quality_report = initial_quality_report(
        ctx=ctx,
        intent=intent,
        semantic_ir=semantic_ir,
        quality_flags=quality_flags,
        render_warnings=render_warnings,
    )
    structural_critic = ir.get("structural_critic")
    if structural_critic:
        evidence = quality_report.setdefault("evidence", {})
        evidence["structural_critic"] = structural_critic
        if structural_critic.get("status") == "warning":
            from app.services.quality import QualityStatus, worst_status

            quality_report["status"] = worst_status(quality_report.get("status"), QualityStatus.warning)
            quality_report.setdefault("warnings", []).append("structural_critic_warning")

    prompt_spec = {
        "title": title,
        "core_message": ctx.normalized_input[:500],
        "visual_description": parsed.parsed_spec.get("structure_summary") or ctx.normalized_input[:500],
        "output_format": "png+svg" if renderer.startswith("structured.") else "png",
        "style": style,
        "must_avoid": must_avoid,
        "visual_requirements": _visual_requirements_for(subtype, renderer),
    }
    visual_json = None
    if visual_plan:
        visual_json = visual_plan.to_prompt_spec()
        prompt_spec.update(visual_json)
        if visual_plan.layout:
            layout_strategy = visual_plan.layout

    if parsed.parsed_spec.get("layout_strategy"):
        layout_strategy = str(parsed.parsed_spec.get("layout_strategy") or layout_strategy)

    return ClassificationRecord(
        diagram_family=intent.diagram_family,
        diagram_subtype=subtype,
        renderer=renderer,
        confidence=intent.confidence,
        understanding_source=intent.source,
        normalized_input=ctx.normalized_input,
        parsed_spec=parsed.parsed_spec,
        visual_plan=visual_json,
        prompt_spec=prompt_spec,
        image_type=image_type,
        subtype=ctx.subtype_hint or subtype,
        style_profile=style_profile_for_book(ctx.style_type),
        render_warnings=render_warnings,
        quality_flags=quality_flags,
        layout_strategy=layout_strategy,
        dsl_json=dsl_json,
        semantic_ir=ir.get("semantic_ir"),
        graph_ir=ir.get("graph_ir"),
        layout_result=ir.get("layout_result"),
        intent_understanding=ir.get("intent_understanding"),
        intent_candidates=intent_candidates,
        quality_report=quality_report,
        pipeline_trace=list(ctx.pipeline_trace or []) or None,
        structural_critic=structural_critic,
    )
