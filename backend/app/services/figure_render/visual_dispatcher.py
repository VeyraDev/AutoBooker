"""统一图像管道分发。"""

from __future__ import annotations

from pathlib import Path

from app.models.book import Book
from app.models.figure import Figure, FigureType
from app.services.figure_render.chart import generate_chart
from app.services.figure_render.figure_ai import generate_figure_image
from app.services.figure_render.figure_prompt_builder import (
    build_figure_prompt_from_template,
    classify_figure_sub_kind,
    llm_expand_image_prompt,
)
from app.services.figure_render.flowchart import generate_flowchart


def resolve_pipeline(intent: str, sub_kind: str | None) -> str:
    if intent in ("gen_flowchart", "regen_figure") and (sub_kind or "") not in (
        "architecture",
        "concept_diagram",
        "illustration",
        "infographic",
    ):
        return "flowchart"
    if intent == "gen_chart":
        return "chart"
    sk = classify_figure_sub_kind("", sub_kind or "")
    if sk == "architecture":
        return "architecture"
    if intent == "gen_figure":
        return "image"
    return "image"


def _pipeline_from_figure(fig: Figure, intent: str, sub_kind: str | None) -> str:
    renderer = (fig.renderer or "").strip().lower()
    if renderer == "need_data":
        raise ValueError("数据可视化需要真实数值，请补充数据或改用文字描述")
    if renderer == "upload":
        raise ValueError("截图类型请手动上传")
    if renderer == "matplotlib":
        return "chart"
    if renderer in ("mermaid", "graphviz"):
        return "flowchart"
    if renderer == "image_api":
        return "image"
    if intent == "regen_figure":
        if fig.figure_type == FigureType.flowchart:
            return "flowchart"
        if fig.figure_type == FigureType.chart:
            return "chart"
        return resolve_pipeline("gen_figure", sub_kind)
    return resolve_pipeline(intent, sub_kind)


def render_figure_asset(
    fig: Figure,
    book: Book,
    out_path: Path,
    *,
    intent: str = "gen_figure",
    chart_type: str | None = None,
    sub_kind: str | None = None,
    model: str = "",
) -> tuple[str, Path]:
    description = (fig.raw_annotation or fig.caption or "").strip()
    pipeline = _pipeline_from_figure(fig, intent, sub_kind)
    book_type = book.book_type.value if book.book_type else ""

    if pipeline == "flowchart":
        return generate_flowchart(
            description,
            out_path,
            model=model,
            book_type=book_type,
        )
    if pipeline == "chart":
        return generate_chart(
            description,
            out_path,
            model=model,
            chart_type_hint=chart_type,
        )
    if pipeline == "architecture":
        sk = "architecture"
        prompt = build_figure_prompt_from_template(
            description, book.style_type or "", sub_kind=sk
        )
        if prompt.startswith("ARCHITECTURE_GRAPHVIZ:"):
            desc = prompt.split(":", 1)[1]
            return generate_flowchart(
                desc,
                out_path,
                model=model,
                book_type=book_type,
            )

    sk = classify_figure_sub_kind(description, sub_kind or "concept_diagram")
    image_prompt = llm_expand_image_prompt(
        description, book.style_type or "", sk
    )
    render_source, png = generate_figure_image(
        image_prompt,
        out_path,
        style_type=book.style_type or "",
        sub_kind=sk,
    )
    return render_source, png
