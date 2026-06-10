"""箭头样式配置。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ArrowStyle:
    name: str
    routing: str  # orthogonal | curved | dataflow | straight
    marker: str = "arrow"
    width_scale: float = 1.0
    dashed_optional: bool = False
    corner_radius: float = 0.0


ARROW_STYLES: dict[str, ArrowStyle] = {
    "orthogonal": ArrowStyle(name="orthogonal", routing="orthogonal", width_scale=1.0),
    "curved": ArrowStyle(name="curved", routing="curved", width_scale=1.0),
    "dataflow": ArrowStyle(name="dataflow", routing="dataflow", width_scale=1.2, corner_radius=4.0),
    "straight": ArrowStyle(name="straight", routing="straight", width_scale=0.9),
    "bidirectional": ArrowStyle(name="bidirectional", routing="curved", width_scale=1.05, dashed_optional=True),
}


def get_arrow_style(name: str) -> ArrowStyle:
    return ARROW_STYLES.get((name or "orthogonal").strip().lower(), ARROW_STYLES["orthogonal"])
