"""Diagram Intent 规则快判。"""

from __future__ import annotations

import re

from app.services.figures.intent.taxonomy import diagram_type_to_subtype, subtype_to_diagram_type
from app.services.figures.schemas.diagram import DiagramIntent


def _intent(family: str, diagram_type: str, confidence: float, source: str, title: str, *, reason: str = "") -> DiagramIntent:
    subtype = diagram_type_to_subtype(diagram_type)
    return DiagramIntent(
        diagram_family=family,
        diagram_subtype=subtype,
        confidence=confidence,
        source=source,
        title=title,
        diagram_type=diagram_type,
        reason=reason or f"关键词匹配为 {diagram_type}",
        fallback_allowed=True,
    )


def _has_numeric_data(text: str) -> bool:
    return bool(
        re.search(r"\d+(?:\.\d+)?\s*%", text)
        or re.search(r"\d{4}\s*年[^\n。；;]*\d+(?:\.\d+)?", text)
        or re.search(r"\|\s*[^|]+\s*\|", text)
        or re.search(r"[:：]\s*\d+(?:\.\d+)?", text)
    )


def _has_workflow_signal(text: str) -> bool:
    return bool(re.search(r"流程|步骤|工作流|pipeline|流水线|链路|用户路径|依次|阶段|环节|→|->|=>|然后|接着|最终|最后", text, re.I))


def _has_comparison_signal(text: str) -> bool:
    return bool(re.search(r"对比|比较|vs\.?|优劣|差异|矩阵|横向比较|纵向比较", text, re.I))


def _has_infographic_signal(text: str) -> bool:
    return bool(re.search(r"信息图|infographic|章节总结|总结图|核心观点|核心要点|知识总结|要点图|图标化|信息块", text, re.I))


def _has_attention_matrix_signal(text: str) -> bool:
    return bool(
        re.search(r"注意力矩阵|attention\s*matrix|attention\s*map|滑动窗口|sliding\s*window|n\s*[×x]\s*n", text, re.I)
        or (
            re.search(r"attention|注意力", text, re.I)
            and re.search(r"矩阵|权重|score|scores|mask|causal|q\s*/?\s*k|qkv|query|key|value|热力|可视化", text, re.I)
        )
    )


def match_diagram_intent(text: str) -> DiagramIntent | None:
    from app.services.figures.pipeline.normalize import strip_layout_instructions

    t, _ = strip_layout_instructions((text or "").strip())
    if not t:
        return None
    d = t.lower()
    title = _title_from_text(t)

    # Data first: never let chart requests fall into generic illustration.
    if re.search(r"柱状图|折线图|饼图|散点图|热力图|数据可视化|bar chart|line chart|pie chart|scatter|heatmap|chart", d, re.I):
        return DiagramIntent("data", "chart", 0.94 if _has_numeric_data(t) else 0.90, "rules", title)

    if re.search(r"决策树|decision\s*tree|是否.*选择|如何选择|是否达标|不达标", d, re.I):
        return _intent("decision", "decision_flow", 0.95, "rules", title)
    if re.search(r"是否|判断|分支|是/否", d) and re.search(r"流程|步骤|训练|评估", d):
        return _intent("decision", "decision_flow", 0.93, "rules", title)
    if re.search(r"根节点", t) and re.search(r"→|->", t):
        return _intent("decision", "decision_flow", 0.94, "rules", title)

    if _has_attention_matrix_signal(t):
        return DiagramIntent("matrix", "attention_matrix", 0.94, "rules", title)
    if re.search(r"swot", d, re.I):
        return DiagramIntent("matrix", "swot", 0.94, "rules", title)
    if _has_comparison_signal(t):
        return DiagramIntent("matrix", "comparison_matrix", 0.93, "rules", title)

    if _has_infographic_signal(t):
        return DiagramIntent("knowledge", "infographic", 0.91, "rules", title, diagram_type="taxonomy", reason="信息图信号", fallback_allowed=True)

    # A domain word plus an ordered chain is still a workflow. Keep this before
    # RAG/Agent architecture aliases so "RAG pipeline: A→B→C" stays a flowchart.
    if re.search(r"调用过程|请求过程|交互过程|客户端.*服务端|时序", d, re.I):
        return _intent("workflow", "sequence", 0.91, "rules", title)
    if re.search(r"数据流|etl|采集|清洗|数据存储|数据分析|数据输出", d, re.I):
        return _intent("workflow", "dataflow", 0.90, "rules", title)
    if _has_workflow_signal(t):
        return _intent("workflow", "flowchart", 0.92, "rules", title)

    if re.search(r"transformer", d, re.I) and re.search(r"编码器|解码器|encoder|decoder|self[-_ ]?attention|cross[-_ ]?attention", d, re.I):
        return DiagramIntent("architecture", "transformer", 0.95, "rules", title)
    if re.search(r"\brag\b|检索增强|向量库|知识库.*大模型|retriever|vector\s*store", d, re.I):
        return DiagramIntent("architecture", "rag", 0.94, "rules", title)
    if re.search(r"agent\s*loop|智能体循环|规划.*执行.*观察|感知.*规划.*行动", d, re.I):
        return DiagramIntent("architecture", "agent", 0.90, "rules", title)

    if re.search(r"时间线|路线图|roadmap|演进|发展阶段|学习路径", d, re.I):
        return DiagramIntent("timeline", "timeline_roadmap", 0.90, "rules", title)
    if re.search(r"组织架构|部门关系|上下级|层级关系", d, re.I):
        return _intent("organization", "hierarchy", 0.91, "rules", title)
    if re.search(r"分类|类型划分|taxonomy|知识体系|图谱|能力地图|思维导图|mind\s*map|章节结构|模块组成", d, re.I):
        return _intent("knowledge", "taxonomy", 0.90, "rules", title)

    if re.search(r"系统架构|产品架构|平台架构|微服务|模块关系|服务层|数据层|应用层|architecture|topology|部署架构|技术架构", d, re.I):
        return _intent("architecture", "architecture", 0.89, "rules", title)

    if re.search(r"机制|原理|如何工作|内部工作|attention|反向传播|embedding|微调|fine[- ]?tuning|rlhf", d, re.I):
        return DiagramIntent("knowledge", "mechanism_diagram", 0.87, "rules", title)

    # Infographic in a book usually contains text; route to structured renderer, not free image API.
    # True scene illustration: atmosphere, people, concrete scenario.
    if re.search(r"场景|插图|插画|氛围|人物|办公室|城市|科幻|未来感|封面", d, re.I):
        return DiagramIntent("illustration", "scene_illustration", 0.86, "rules", title)

    if re.search(r"概念|关系|示意图|核心逻辑|商业逻辑|方法论", d, re.I):
        return DiagramIntent("knowledge", "concept_diagram", 0.78, "rules", title)

    return None


def _title_from_text(text: str) -> str:
    first = text.split("。")[0].split("\n")[0].strip()
    return (first[:80] + "…") if len(first) > 80 else first


def default_intent_for_hint(subtype_hint: str | None) -> DiagramIntent | None:
    h = (subtype_hint or "").strip().lower()
    if h in {"chapter_summary", "infographic"}:
        return DiagramIntent("knowledge", "infographic", 0.9, "hint", "章节总结信息图")
    if h in {"scene_illustration", "case_scene", "future_scene"}:
        return DiagramIntent("illustration", "scene_illustration", 0.9, "hint", "场景插图")
    if h in {
        "concept_diagram",
        "mechanism_diagram",
        "process_flow",
        "system_architecture",
        "comparison_matrix",
        "taxonomy_map",
        "timeline_roadmap",
        "decision_tree",
    }:
        family = "knowledge"
        if h == "process_flow":
            family = "workflow"
        elif h == "system_architecture":
            family = "architecture"
        elif h == "decision_tree":
            family = "decision"
        elif h == "comparison_matrix":
            family = "matrix"
        elif h == "timeline_roadmap":
            family = "timeline"
        return DiagramIntent(
            family,
            h,
            0.9,
            "hint",
            "",
            diagram_type=subtype_to_diagram_type(h),
            reason="subtype_hint",
            fallback_allowed=True,
        )
    return None
