"""按 classification_json.renderer 分发渲染。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from app.models.book import Book
from app.models.figure import Figure
from app.services.figures.pipeline.helpers import spec_to_flowchart_description
from app.services.figures.classification.legacy_adapter import normalize_renderer_key
from app.services.figures.intent.taxonomy import (
    RENDERER_ILLUSTRATION,
    RENDERER_NEED_DATA,
    RENDERER_STRUCTURED_ARCHITECTURE,
    RENDERER_STRUCTURED_CHART,
    RENDERER_STRUCTURED_COMPARISON,
    RENDERER_STRUCTURED_FLOWCHART,
    RENDERER_STRUCTURED_GENERIC,
    RENDERER_STRUCTURED_INFOGRAPHIC,
    RENDERER_STRUCTURED_MATRIX,
    RENDERER_STRUCTURED_NETWORK,
    RENDERER_STRUCTURED_RAG,
    RENDERER_STRUCTURED_SWOT,
    RENDERER_STRUCTURED_TAXONOMY,
    RENDERER_STRUCTURED_TIMELINE,
    RENDERER_STRUCTURED_TRANSFORMER,
    RENDERER_UPLOAD,
)
from app.services.figures.render.illustration.provider import generate_figure_image
from app.services.figures.render.illustration.visual_prompt import visual_plan_to_prompt
from app.services.figures.render.structured.chart import generate_chart
from app.services.figures.render.structured.decision_flow import generate_decision_flow_diagram
from app.services.figures.render.structured.flowchart import generate_flowchart
from app.services.figures.render.structured.grammar import (
    generate_architecture_diagram,
    generate_comparison_diagram,
    generate_infographic_diagram,
    generate_network_diagram,
    generate_taxonomy_diagram,
    generate_timeline_diagram,
)
from app.services.figures.render.structured.generic_graph import generate_structured_diagram
from app.services.figures.render.structured.matrix import generate_matrix_diagram
from app.services.figures.render.structured.rag import generate_rag_diagram
from app.services.figures.render.structured.swot import generate_swot_diagram
from app.services.figures.render.structured.transformer import generate_transformer_architecture
from app.services.figure_render.figure_structure import has_structured_graph

_SVG_FIRST_RENDERERS = frozenset({
    RENDERER_STRUCTURED_GENERIC,
    RENDERER_STRUCTURED_FLOWCHART,
    RENDERER_STRUCTURED_ARCHITECTURE,
    RENDERER_STRUCTURED_NETWORK,
    RENDERER_STRUCTURED_RAG,
    RENDERER_STRUCTURED_COMPARISON,
    RENDERER_STRUCTURED_TAXONOMY,
    RENDERER_STRUCTURED_TIMELINE,
    RENDERER_STRUCTURED_MATRIX,
    RENDERER_STRUCTURED_TRANSFORMER,
    RENDERER_STRUCTURED_INFOGRAPHIC,
})


def _matplotlib_backend() -> bool:
    return os.environ.get("FIGURE_RENDER_BACKEND", "svg").strip().lower() == "matplotlib"


def _try_svg_render(spec: dict, out_path: Path, *, title: str, clf: dict) -> tuple[str, Path] | None:
    if _matplotlib_backend():
        return None
    layout_result = clf.get("layout_result") or spec.get("layout_result")
    if not layout_result and not spec.get("nodes"):
        return None
    try:
        from app.services.figures.render.svg.renderer import render_svg_diagram

        theme = str((spec.get("style") or clf.get("dsl_json") or {}).get("theme") or "modern_saas")
        if isinstance(clf.get("dsl_json"), dict):
            theme = str((clf["dsl_json"].get("style") or {}).get("theme") or theme)
        return render_svg_diagram(spec, out_path, title=title, layout_result=layout_result, theme=theme)
    except Exception:
        return None


def _svg_first_or_fallback(
    spec: dict,
    out_path: Path,
    *,
    title: str,
    clf: dict,
    fallback: Callable[[], tuple[str, Path]],
) -> tuple[str, Path]:
    """结构图优先 SVG，Matplotlib/旧 renderer 仅作兜底。"""
    if has_structured_graph(spec):
        svg_out = _try_svg_render(spec, out_path, title=title, clf=clf)
        if svg_out:
            return svg_out
    return fallback()


def _clf(fig: Figure) -> dict[str, Any]:
    c = fig.classification_json
    return c if isinstance(c, dict) else {}


def _parsed_spec(fig: Figure) -> dict[str, Any]:
    spec = _clf(fig).get("parsed_spec")
    if isinstance(spec, dict) and spec:
        return spec
    dsl = _clf(fig).get("dsl_json")
    if isinstance(dsl, dict) and dsl.get("nodes"):
        from app.services.figures.dsl.to_parsed_spec import dsl_to_parsed_spec
        from app.services.figures.schemas.dsl import DiagramDSL

        return dsl_to_parsed_spec(DiagramDSL.from_dict(dsl))
    return {}


def _title(fig: Figure) -> str:
    ps = _clf(fig).get("prompt_spec") or {}
    return str(ps.get("title") or "")


def _normalized(fig: Figure) -> str:
    return _clf(fig).get("normalized_input") or (fig.raw_annotation or fig.caption or "").strip()


def render_figure(fig: Figure, book: Book, out_path: Path, *, model: str = "", chart_type: str | None = None) -> tuple[str, Path]:
    renderer = normalize_renderer_key(fig.renderer or _clf(fig).get("renderer"))
    spec = _parsed_spec(fig)
    title = _title(fig)
    description = _normalized(fig)
    book_type = book.book_type.value if book.book_type else ""
    clf = _clf(fig)

    if renderer == RENDERER_UPLOAD:
        raise ValueError("截图类型请手动上传")
    if renderer == RENDERER_NEED_DATA:
        raise ValueError("数据图缺少可解析的数值，请编辑标注后重试")

    if renderer == RENDERER_STRUCTURED_GENERIC:
        if has_structured_graph(spec):
            diagram_type = str(clf.get("diagram_type") or fig.subtype or "")
            if diagram_type in {"decision_flow", "decision_tree"}:
                return _svg_first_or_fallback(
                    spec, out_path, title=title, clf=clf,
                    fallback=lambda: generate_decision_flow_diagram(spec, out_path, title=title),
                )
            return _svg_first_or_fallback(
                spec, out_path, title=title, clf=clf,
                fallback=lambda: generate_structured_diagram(spec, out_path, title=title),
            )
        raise ValueError("structured.generic_graph 缺少 nodes/edges")

    if renderer == RENDERER_STRUCTURED_TIMELINE:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_timeline_diagram(spec, out_path, title=title),
        )

    if renderer == RENDERER_STRUCTURED_TAXONOMY:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_taxonomy_diagram(spec, out_path, title=title),
        )

    if renderer == RENDERER_STRUCTURED_COMPARISON:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_comparison_diagram(spec, out_path, title=title),
        )

    if renderer == RENDERER_STRUCTURED_ARCHITECTURE:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_architecture_diagram(spec, out_path, title=title),
        )

    if renderer == RENDERER_STRUCTURED_NETWORK:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_network_diagram(spec, out_path, title=title),
        )

    if renderer == RENDERER_STRUCTURED_INFOGRAPHIC:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_infographic_diagram(spec, out_path, title=title),
        )

    if renderer == RENDERER_STRUCTURED_TRANSFORMER:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_transformer_architecture(description, out_path, render_spec=spec, title=title),
        )

    if renderer == RENDERER_STRUCTURED_RAG:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_rag_diagram(spec, out_path, title=title),
        )

    if renderer == RENDERER_STRUCTURED_SWOT:
        return generate_swot_diagram(spec, out_path, title=title)

    if renderer == RENDERER_STRUCTURED_MATRIX:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_matrix_diagram(description, out_path, render_spec=spec),
        )

    if renderer == RENDERER_STRUCTURED_FLOWCHART:
        if has_structured_graph(spec):
            return _svg_first_or_fallback(
                spec, out_path, title=title, clf=clf,
                fallback=lambda: generate_structured_diagram(spec, out_path, title=title),
            )
        image_type = fig.image_type or "process_flow"
        return generate_flowchart(description, out_path, model=model, book_type=book_type, image_type=image_type)

    if renderer == RENDERER_STRUCTURED_CHART:
        return generate_chart(description, out_path, model=model, chart_type_hint=chart_type, render_spec=spec)

    if renderer == RENDERER_ILLUSTRATION:
        visual = clf.get("visual_plan") or clf.get("prompt_spec") or {}
        from app.services.figures.schemas.diagram import VisualPlan

        plan = VisualPlan(
            layout=str(visual.get("layout") or ""),
            style=str(visual.get("style") or ""),
            visual_description=str(visual.get("visual_description") or visual.get("core_message") or description[:400]),
            must_include=list(visual.get("must_include") or []),
            must_avoid=list(visual.get("must_avoid") or []),
        )
        prompt = visual_plan_to_prompt(plan, style_type=book.style_type or "")
        sub = fig.subtype or "concept_diagram"
        return generate_figure_image(prompt, out_path, style_type=book.style_type or "", sub_kind=sub)

    if has_structured_graph(spec):
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_structured_diagram(spec, out_path, title=title),
        )

    raise ValueError(f"无法渲染：未知 renderer={renderer}")
