"""Component variant 注册表。"""

from __future__ import annotations

from app.services.figures.design.variants.architecture import ARCHITECTURE
from app.services.figures.design.variants.base import VariantStyle
from app.services.figures.design.variants.comparison import COMPARISON_VARIANTS
from app.services.figures.design.variants.default import DEFAULT
from app.services.figures.design.variants.flow import FLOW
from app.services.figures.design.variants.mechanism import MECHANISM
from app.services.figures.design.variants.pipeline import PIPELINE
from app.services.figures.design.variants.swimlane import SWIMLANE
from app.services.figures.design.variants.timeline import TIMELINE
from app.services.figures.design.variants.tree import TREE

_VARIANTS: dict[str, VariantStyle] = {
    "default": DEFAULT,
    "flow": FLOW,
    "architecture": ARCHITECTURE,
    "mechanism": MECHANISM,
    "pipeline": PIPELINE,
    "tree": TREE,
    "timeline": TIMELINE,
    "swimlane": SWIMLANE,
    **COMPARISON_VARIANTS,
}


def get_variant_config(name: str) -> VariantStyle:
    key = (name or "default").strip().lower()
    return _VARIANTS.get(key, DEFAULT)
