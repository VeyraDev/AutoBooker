"""Deterministic image_type → renderer mapping."""

from __future__ import annotations

import re
from typing import Any

STYLE_BY_BOOK: dict[str, str] = {
    "popular_science": "book_diagram_minimal",
    "insight_opinion": "book_diagram_minimal",
    "practical_guide": "book_diagram_bluegray",
    "reference_tool": "book_diagram_bluegray",
    "academic_monograph": "book_diagram_minimal",
    "textbook": "book_diagram_textbook",
}


def style_profile_for_book(style_type: str | None) -> str:
    st = (style_type or "").strip()
    return STYLE_BY_BOOK.get(st, "book_diagram_minimal")


def infer_image_type_from_text(description: str) -> str:
    d = description.lower()
    if re.search(r"决策树|decision\s*tree|decision_tree", description, re.I):
        return "decision_tree"
    if re.search(r"根节点", description) and re.search(r"→|->", description):
        return "decision_tree"
    arrow_branches = len(re.findall(r"→|->", description))
    if arrow_branches >= 2 and re.search(r"选择|核心优势|分支", description):
        return "decision_tree"
    if re.search(r"注意力矩阵|滑动窗口|n\s*[×x]\s*n|attention\s*matrix|sliding\s*window", d, re.I):
        return "matrix_diagram"
    if re.search(r"柱状图|折线图|饼图|散点图|热力图|%\s*\d|数据可视化|chart|bar chart|line chart", d):
        return "data_visualization"
    if re.search(r"transformer|编码器.*解码器|encoder.*decoder|残差.*层归一化", d, re.I):
        return "mechanism_diagram"
    if re.search(r"架构|系统组成|模块|rag|agent\s*loop|topology|architecture", d, re.I):
        return "system_architecture"
    if re.search(r"流程|步骤|pipeline|工作流|→|->", d):
        return "process_flow"
    if re.search(r"对比|矩阵|vs\.|优劣", d):
        return "comparison_matrix"
    if re.search(r"分类|taxonomy|类型划分", d):
        return "taxonomy_map"
    if re.search(r"时间线|路线图|roadmap|演进", d):
        return "timeline_roadmap"
    if re.search(r"机制|原理|attention|反向传播", d, re.I):
        return "mechanism_diagram"
    if re.search(r"场景|插图|氛围|插画", d):
        return "scene_illustration"
    if re.search(r"信息图|总结图|infographic", d, re.I):
        return "infographic"
    return "concept_diagram"


def is_transformer_architecture(description: str) -> bool:
    d = description.lower()
    return bool(
        re.search(r"transformer", d, re.I)
        and re.search(r"编码器|解码器|encoder|decoder", d, re.I)
    )


def resolve_renderer(
    image_type: str,
    *,
    has_numeric_data: bool,
    description: str = "",
    render_spec: dict | None = None,
) -> str:
    from app.services.figures.render.legacy_svg.figure_structure import has_structured_graph

    if render_spec and has_structured_graph(render_spec):
        return "structured_template"
    if image_type == "matrix_diagram":
        return "matrix_template"
    if image_type == "decision_tree":
        return "structured_template"
    if image_type == "mechanism_diagram" and is_transformer_architecture(description):
        return "transformer_template"
    if image_type == "data_visualization":
        return "matplotlib" if has_numeric_data else "need_data"
    if image_type in (
        "process_flow",
        "system_architecture",
        "taxonomy_map",
        "timeline_roadmap",
        "comparison_matrix",
        "mechanism_diagram",
        "concept_diagram",
    ):
        return "graphviz"
    if image_type == "scene_illustration":
        return "image_api"
    if image_type == "infographic":
        return "image_api"
    return "graphviz"


def has_numeric_data_signal(text: str) -> bool:
    """Detect explicit numeric data, not just a casual number in prose."""
    t = text or ""
    return bool(
        re.search(r"\d+(?:\.\d+)?\s*%", t)
        or re.search(r"\d{4}\s*年[^\n。；;]*\d+(?:\.\d+)?", t)
        or re.search(r"[:：]\s*\d+(?:\.\d+)?", t)
        or re.search(r"\|\s*[^|]+\s*\|", t)
        or len(re.findall(r"\d+(?:\.\d+)?", t)) >= 4
    )


def legacy_tag_to_figure_type(tag: str) -> str:
    t = tag.upper()
    if t == "CHART":
        return "chart"
    if t == "FLOWCHART":
        return "flowchart"
    if t == "SCREENSHOT":
        return "screenshot"
    return "figure"


def build_classification(
    description: str,
    *,
    style_type: str | None = None,
    legacy_tag: str | None = None,
    subtype_hint: str | None = None,
) -> dict[str, Any]:
    if subtype_hint == "chapter_summary":
        image_type = "infographic"
    elif legacy_tag:
        ft = legacy_tag_to_figure_type(legacy_tag)
        inferred = infer_image_type_from_text(description)
        if ft == "chart":
            image_type = "data_visualization"
        elif ft == "flowchart":
            image_type = inferred if inferred not in ("concept_diagram", "scene_illustration", "infographic") else "process_flow"
        elif ft == "screenshot":
            image_type = "screenshot"
        else:
            image_type = inferred
    else:
        image_type = infer_image_type_from_text(description)

    if (description or "").strip().upper().startswith("SCREENSHOT"):
        image_type = "screenshot"

    numeric = has_numeric_data_signal(description)
    renderer = resolve_renderer(image_type, has_numeric_data=numeric, description=description)
    if image_type == "screenshot":
        renderer = "upload"

    return {
        "image_type": image_type,
        "subtype": subtype_hint or "",
        "purpose": "explain",
        "audience_level": "semi_technical",
        "renderer": renderer,
        "style_profile": style_profile_for_book(style_type),
        "text_density": "medium",
        "data_required": image_type == "data_visualization",
        "prompt_spec": {
            "title": description[:120],
            "core_message": description[:500],
            "must_include": [],
            "must_avoid": ["复杂代码", "照片风格"] if image_type != "scene_illustration" else [],
            "layout": "left_to_right",
            "style": "white background, unified blue-gray color blocks, subtle icon badges, generous spacing, clean vector lines",
            "output_format": "png",
        },
    }
