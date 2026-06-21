"""兼容 shim → figures 包。"""

from app.services.figures.pipeline.helpers import spec_to_flowchart_description
from app.services.figures.pipeline.normalize import normalize_figure_input
from app.services.figures.pipeline.orchestrator import (
    apply_classification_to_figure,
    classify_and_persist,
    classify_figure_description,
)

__all__ = [
    "apply_classification_to_figure",
    "classify_and_persist",
    "classify_figure_description",
    "get_image_prompt",
    "get_render_description",
    "get_render_spec",
    "normalize_figure_input",
    "prepare_figure_classification",
    "spec_to_flowchart_description",
    "understand_and_classify",
]


def prepare_figure_classification(fig, **kwargs):
    desc = (fig.raw_annotation or fig.caption or "").strip()
    return classify_figure_description(desc, figure_annotation=fig.raw_annotation or "", **kwargs)


def understand_and_classify(description: str, **kwargs):
    return classify_figure_description(description, **kwargs)


def get_render_spec(fig):
    clf = fig.classification_json if isinstance(fig.classification_json, dict) else {}
    spec = clf.get("parsed_spec")
    return spec if isinstance(spec, dict) else {}


def get_render_description(fig):
    clf = fig.classification_json if isinstance(fig.classification_json, dict) else {}
    spec = get_render_spec(fig)
    if spec.get("nodes"):
        return spec_to_flowchart_description(spec, title=str((clf.get("prompt_spec") or {}).get("title") or ""))
    return clf.get("normalized_input") or (fig.raw_annotation or fig.caption or "").strip()


def get_image_prompt(fig, *, style_type: str = ""):
    from app.services.figures.render.illustration.visual_prompt import visual_plan_to_prompt
    from app.services.figures.schemas.diagram import VisualPlan

    clf = fig.classification_json if isinstance(fig.classification_json, dict) else {}
    visual = clf.get("visual_plan") or clf.get("prompt_spec") or {}
    plan = VisualPlan(
        layout=str(visual.get("layout") or ""),
        style=str(visual.get("style") or ""),
        visual_description=str(visual.get("visual_description") or visual.get("core_message") or ""),
    )
    return visual_plan_to_prompt(plan, style_type=style_type)
