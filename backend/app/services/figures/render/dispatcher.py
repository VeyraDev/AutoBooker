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
    RENDERER_GENERIC_COMPOSITOR,
    RENDERER_INFOGRAPHIC_TEMPLATE,
    RENDERER_ILLUSTRATION,
    RENDERER_NEED_DATA,
    RENDERER_STRUCTURED_ARCHITECTURE,
    RENDERER_STRUCTURED_CHART,
    RENDERER_STRUCTURED_COMPARISON,
    RENDERER_STRUCTURED_DUAL_STACK,
    RENDERER_STRUCTURED_FLOWCHART,
    RENDERER_STRUCTURED_GENERIC,
    RENDERER_STRUCTURED_INFOGRAPHIC,
    RENDERER_STRUCTURED_MATRIX,
    RENDERER_STRUCTURED_NETWORK,
    RENDERER_STRUCTURED_SWOT,
    RENDERER_STRUCTURED_TAXONOMY,
    RENDERER_STRUCTURED_THREE_COLUMN,
    RENDERER_STRUCTURED_TIMELINE,
    RENDERER_UPLOAD,
)
from app.services.figures.render.illustration.provider import generate_figure_image
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
from app.services.figures.render.result import FigureRenderResult, coerce_render_result
from app.services.figures.render.structured.swot import generate_swot_diagram
from app.services.figures.render.structured.transformer import generate_transformer_architecture
from app.services.figures.render.legacy_svg.figure_structure import has_structured_graph
from app.services.figures.render.html_template import render_infographic_spec
from app.services.figures.render.compositor import render_composited_diagram
from app.services.figures.render.image_api.prompt_constraints import IMAGE_API_SUBTYPES

_SVG_FIRST_RENDERERS = frozenset({
    RENDERER_STRUCTURED_GENERIC,
    RENDERER_STRUCTURED_FLOWCHART,
    RENDERER_STRUCTURED_ARCHITECTURE,
    RENDERER_STRUCTURED_NETWORK,
    RENDERER_STRUCTURED_COMPARISON,
    RENDERER_STRUCTURED_TAXONOMY,
    RENDERER_STRUCTURED_TIMELINE,
    RENDERER_STRUCTURED_MATRIX,
    RENDERER_STRUCTURED_DUAL_STACK,
    RENDERER_STRUCTURED_THREE_COLUMN,
    RENDERER_STRUCTURED_INFOGRAPHIC,
})


def _matplotlib_backend() -> bool:
    return os.environ.get("FIGURE_RENDER_BACKEND", "svg").strip().lower() == "matplotlib"


LegacyRenderReturn = tuple[str, Path]


def _finish(result: FigureRenderResult | LegacyRenderReturn, out_path: Path) -> FigureRenderResult:
    if isinstance(result, FigureRenderResult):
        return result
    render_source, path = result
    return coerce_render_result(render_source, path, out_path.with_suffix(".png"))


def _resolve_design_spec(spec: dict, clf: dict) -> dict:
    ds = spec.get("design_spec") or clf.get("design_spec")
    if isinstance(ds, dict) and ds:
        return ds
    style = spec.get("style") if isinstance(spec.get("style"), dict) else {}
    dsl = clf.get("dsl_json") if isinstance(clf.get("dsl_json"), dict) else {}
    dsl_style = dsl.get("style") if isinstance(dsl.get("style"), dict) else {}
    theme = str(dsl_style.get("theme") or style.get("theme") or "modern_saas")
    return {
        "theme": theme,
        "component_variant": str(dsl_style.get("component_variant") or style.get("component_variant") or "default"),
        "container_style": str(dsl_style.get("container_style") or style.get("container_style") or "rounded"),
        "arrow_style": str(dsl_style.get("arrow_style") or style.get("arrow_style") or "orthogonal"),
        "annotation_style": str(dsl_style.get("annotation_style") or style.get("annotation_style") or "minimal"),
    }


def _try_svg_render(spec: dict, out_path: Path, *, title: str, clf: dict) -> FigureRenderResult | None:
    if _matplotlib_backend():
        return None
    design_spec = _resolve_design_spec(spec, clf)
    from app.services.figures.contracts.renderer_profiles import select_render_profile

    profile = str(spec.get("render_profile") or select_render_profile(spec))
    if not spec.get("render_profile"):
        spec = dict(spec)
        spec["render_profile"] = profile
        if "legacy_spec_migrated" not in (spec.get("quality_flags") or []):
            spec.setdefault("quality_flags", []).append("legacy_spec_migrated")

    if profile == "svg.matrix":
        try:
            from app.services.figures.render.svg.comparison import render_comparison_svg

            return _finish(render_comparison_svg(spec, out_path, title=title, design_spec=design_spec), out_path)
        except Exception:
            return None

    if profile == "svg.timeline":
        try:
            from app.services.figures.render.svg.timeline import render_timeline_svg

            return _finish(render_timeline_svg(spec, out_path, title=title, design_spec=design_spec), out_path)
        except Exception:
            return None

    if profile == "svg.blocks":
        try:
            from app.services.figures.render.svg.comparison import render_comparison_svg

            ctx_spec = dict(spec)
            ctx_spec["component_variant"] = "cards"
            return _finish(render_comparison_svg(ctx_spec, out_path, title=title, design_spec=design_spec), out_path)
        except Exception:
            return None

    if profile in {"svg.flow", "svg.architecture", "svg.mechanism", "svg.radial", "svg.network", "svg.decision"} and spec.get("nodes"):
        try:
            from app.services.figures.render.svg.graph_grammar import render_graph_grammar_svg

            return _finish(render_graph_grammar_svg(spec, out_path, title=title, design_spec=design_spec), out_path)
        except Exception:
            return None

    layout_result = clf.get("layout_result") or spec.get("layout_result")
    if profile in {"svg.graph", "svg.tree", "svg.swimlane"} and layout_result and spec.get("nodes"):
        try:
            from app.services.figures.render.svg.renderer import render_svg_diagram

            theme = str(design_spec.get("theme") or "modern_saas")
            return _finish(
                render_svg_diagram(
                    spec,
                    out_path,
                    title=title,
                    layout_result=layout_result,
                    theme=theme,
                    design_spec=design_spec,
                ),
                out_path,
            )
        except Exception:
            return None
    return None


def _svg_first_or_fallback(
    spec: dict,
    out_path: Path,
    *,
    title: str,
    clf: dict,
    fallback: Callable[[], LegacyRenderReturn | FigureRenderResult],
) -> FigureRenderResult:
    """结构图优先 SVG，Matplotlib/旧 renderer 仅作兜底。"""
    if has_structured_graph(spec) or (spec.get("render_profile") == "svg.swimlane" and spec.get("lanes") and spec.get("nodes")):
        svg_out = _try_svg_render(spec, out_path, title=title, clf=clf)
        if svg_out:
            return svg_out
    return _finish(fallback(), out_path)


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


def render_figure(fig: Figure, book: Book, out_path: Path, *, model: str = "", chart_type: str | None = None) -> FigureRenderResult:
    renderer = normalize_renderer_key(fig.renderer or _clf(fig).get("renderer"))
    spec = _parsed_spec(fig)
    # 图题由正文题注承载，图片画布内部不再渲染置顶大标题。
    title = ""
    description = _normalized(fig)
    book_type = book.book_type.value if book.book_type else ""
    clf = _clf(fig)
    declared_subtype = str(fig.subtype or clf.get("diagram_subtype") or fig.image_type or "").strip().lower()
    if declared_subtype == "screenshot":
        renderer = RENDERER_UPLOAD
    elif renderer != RENDERER_ILLUSTRATION:
        renderer = RENDERER_ILLUSTRATION

    if spec.get("render_mode") == "needs_clarification":
        messages = spec.get("compiler_messages") or ["输入缺少可排版结构，需要补充信息"]
        raise ValueError("；".join(str(x) for x in messages if str(x).strip()))

    if renderer == RENDERER_UPLOAD:
        raise ValueError("截图类型请手动上传")
    if renderer == RENDERER_NEED_DATA:
        return _finish(
            generate_chart(description, out_path, model=model, chart_type_hint=chart_type, render_spec=spec),
            out_path,
        )

    if renderer == RENDERER_STRUCTURED_CHART:
        return _finish(generate_chart(description, out_path, model=model, chart_type_hint=chart_type, render_spec=spec), out_path)

    if renderer == RENDERER_ILLUSTRATION:
        sub = declared_subtype if declared_subtype in IMAGE_API_SUBTYPES else "concept_diagram"
        source_text = str(
            spec.get("image_input")
            or clf.get("image_input")
            or (clf.get("prompt_spec") or {}).get("image_input")
            or fig.raw_annotation
            or clf.get("normalized_input")
            or fig.caption
            or ""
        ).strip()
        prompt_mode = str(
            spec.get("prompt_mode")
            or clf.get("prompt_mode")
            or (clf.get("prompt_spec") or {}).get("prompt_mode")
            or ""
        ).strip() or None
        return _finish(
            generate_figure_image(
                source_text,
                out_path,
                style_type=book.style_type or "",
                sub_kind=sub,
                layout_script=None,
                prompt_mode=prompt_mode,
            ),
            out_path,
        )

    if renderer == RENDERER_INFOGRAPHIC_TEMPLATE:
        diagram_spec = spec.get("diagram_spec") if isinstance(spec.get("diagram_spec"), dict) else spec
        return render_infographic_spec(diagram_spec, out_path, subtype=str(fig.subtype or clf.get("diagram_subtype") or ""))

    if renderer == RENDERER_GENERIC_COMPOSITOR or spec.get("render_mode") == "generic_compositor":
        return render_composited_diagram(
            spec,
            out_path,
            subtype=str(fig.subtype or clf.get("diagram_subtype") or ""),
            title=title,
        )

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
        if spec.get("blocks"):
            return _finish(generate_infographic_diagram(spec, out_path, title=title), out_path)
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_infographic_diagram(spec, out_path, title=title),
        )

    if renderer == RENDERER_STRUCTURED_DUAL_STACK:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_transformer_architecture(description, out_path, render_spec=spec, title=title),
        )

    if renderer == RENDERER_STRUCTURED_THREE_COLUMN:
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_rag_diagram(spec, out_path, title=title),
        )

    if renderer == RENDERER_STRUCTURED_SWOT:
        return _finish(generate_swot_diagram(spec, out_path, title=title), out_path)

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
        return _finish(generate_flowchart(description, out_path, model=model, book_type=book_type, image_type=image_type), out_path)

    if has_structured_graph(spec):
        return _svg_first_or_fallback(
            spec, out_path, title=title, clf=clf,
            fallback=lambda: generate_structured_diagram(spec, out_path, title=title),
        )

    raise ValueError(f"无法渲染：未知 renderer={renderer}")
