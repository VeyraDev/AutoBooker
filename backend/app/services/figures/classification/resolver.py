"""parsed_spec + intent → ClassificationRecord。"""

from __future__ import annotations

import re

from app.services.figures.render.legacy_svg.renderer_rules import has_numeric_data_signal, style_profile_for_book
from app.services.figures.quality import initial_quality_report, intent_candidate_report
from app.services.figures.intent.taxonomy import (
    RENDERER_ILLUSTRATION,
    RENDERER_STRUCTURED_CHART,
    RENDERER_UPLOAD,
    SUBTYPE_TO_LEGACY_IMAGE_TYPE,
    resolve_renderer_key,
)
from app.services.figures.render.image_api.prompt_constraints import IMAGE_API_SUBTYPES
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
        "清晰流程图；步骤节点使用圆角矩形；短流程优先横向，长流程优先纵向或蛇形折返；"
        "节点间距充足，节点宽度随文字长度调整；判断节点与步骤节点形状区分；"
        "返回、反馈或重试关系使用较轻线条或虚线；起止节点使用胶囊形"
    ),
    "system_architecture": (
        "分层或分区架构图；每个层级使用带标题的浅色容器；模块使用白底卡片和细边框；"
        "入口、核心处理、共享基础设施、外部对象视觉层级清楚；"
        "跨层箭头保持细而明确，相关连接先分组再连接，避免线条缠绕"
    ),
    "decision_tree": (
        "自上而下决策树；判断节点使用菱形或强调形状，结果节点使用圆角矩形；"
        "分支标签靠近分叉点；层级之间留出足够纵向间距；根节点更醒目，同层节点宽度一致"
    ),
    "comparison_matrix": (
        "稳定行列矩阵或并列卡片；比较对象和比较维度固定在清楚轴线上；"
        "表头加粗，对应单元格对齐；同一维度的信息结构一致；"
        "重点结论可用浅色底强调，但不依赖颜色单独表达逻辑"
    ),
    "timeline_roadmap": (
        "水平或纵向时间轴；时间标签锚定在主轴上；事件标题与说明分层显示；"
        "节点标签可上下交错避免重叠；阶段分组可使用浅色带状背景"
    ),
    "taxonomy_map": (
        "树形、缩进或放射分类图；根节点最大，一级分类次之，成员节点最小；"
        "同一父节点下成员靠近并对齐；连接线表示归属，不使用流程箭头"
    ),
    "infographic": (
        "信息卡片或分组网格；每个信息块高度一致；标题、图标、说明对齐；"
        "多个分组先显示主题或分类，再显示模块；卡片之间保持清楚组织关系"
    ),
    "chart": (
        "数据图表；根据数据形态选择柱状、折线、饼图或散点；坐标轴、标签和图例清楚；"
        "网格线轻量，数据标签避免重叠；单系列优先使用同一色系"
    ),
    "concept_diagram": (
        "概念关系图；核心概念更醒目，相关概念按类别或关系分组；"
        "关系标签靠近连线，同级概念视觉等级一致；布局优先表达语义而非对称"
    ),
    "mechanism_diagram": (
        "机制原理图；输入、内部对象、中间状态、控制量和输出分区清楚；"
        "关键对象使用形状、对齐、括号或公式关系表达；不同作用关系使用不同线型或位置"
    ),
    "scene_illustration": (
        "书籍正文概念插图；默认少字或无字；使用单一主视觉表达核心概念；"
        "避免流程框、复杂箭头和大量标签；前景与背景层次清楚"
    ),
}

_DEFAULT_STYLE = (
    "书籍正文图示；浅色背景；统一节点填充、细边框、清楚标题、充足间距；"
    "不使用装饰背景，优先保证结构、文字和连接关系清晰"
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
    st = str(subtype or "").strip().lower()
    if st not in (set(IMAGE_API_SUBTYPES) | {"chart", "screenshot"}):
        st = "concept_diagram"
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
        if subtype == "scene_illustration":
            return ["场景氛围优先", "默认不出现文字标注框", "构图有前景/背景层次"]
        return base + ["严格使用布局脚本中的可见文字白名单", "文字清晰完整，不翻译、不改写、不裁切"]
    subtype_extras = {
        "process_flow": ["步骤节点等高等宽", "决策菱形与步骤矩形形状明确区分", "反馈边用虚线"],
        "system_architecture": ["层容器背景区分明显", "跨层箭头不交叉", "网关/入口节点用强调色"],
        "comparison_matrix": ["每列颜色独立", "表头加粗", "对比维度左对齐"],
        "infographic": ["每个信息块等高", "图标与文字对齐", "最多2×4格布局"],
        "timeline_roadmap": ["时间轴水平居中", "里程碑标签交错上下避免重叠", "阶段带状背景"],
        "decision_tree": ["根节点居顶居中", "同层节点等高", "叶节点用不同背景色标记结果"],
        "taxonomy_map": ["根节点最大", "子节点按层递减", "连线用曲线而非折线"],
        "chart": ["坐标轴标注清晰", "数据标签避免重叠", "单系列用单色渐变"],
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
    subtype = str(intent.diagram_subtype or "").strip().lower()
    if subtype not in (set(IMAGE_API_SUBTYPES) | {"chart", "screenshot"}):
        subtype = "concept_diagram"
    if subtype == "data_visualization":
        subtype = "chart"

    numeric = has_numeric_data_signal(ctx.normalized_input)
    if parsed.parsed_spec.get("values") or parsed.parsed_spec.get("series"):
        numeric = True

    renderer = resolve_renderer_key(subtype, has_numeric_data=numeric)
    if subtype == "chart":
        renderer = RENDERER_STRUCTURED_CHART
    elif subtype == "screenshot":
        renderer = RENDERER_UPLOAD
    else:
        renderer = RENDERER_ILLUSTRATION

    image_type = SUBTYPE_TO_LEGACY_IMAGE_TYPE.get(subtype, "concept_diagram")

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
        must_avoid.extend(["伪造截图", "翻译文字", "新增标签", "裁切文字"])
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
    for key in (
        "primary_type",
        "secondary_type",
        "do_not_draw_as",
        "layout_risks",
        "layout_script",
        "layout_agent_fallback",
    ):
        if key in parsed.parsed_spec:
            prompt_spec[key] = parsed.parsed_spec.get(key)
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
        subtype=subtype,
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
