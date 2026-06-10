"""容器样式配置。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContainerStyle:
    name: str
    rx: int
    fill_opacity: float = 1.0
    stroke_dashed: bool = False
    header_band: bool = False
    pipeline_stage: bool = False


CONTAINER_STYLES: dict[str, ContainerStyle] = {
    "rounded": ContainerStyle(name="rounded", rx=12),
    "sharp": ContainerStyle(name="sharp", rx=2),
    "pipeline_stage": ContainerStyle(name="pipeline_stage", rx=4, header_band=True, pipeline_stage=True),
    "lane": ContainerStyle(name="lane", rx=0, stroke_dashed=True, fill_opacity=0.85),
    "minimal": ContainerStyle(name="minimal", rx=8, fill_opacity=0.6),
}


def get_container_style(name: str) -> ContainerStyle:
    return CONTAINER_STYLES.get((name or "rounded").strip().lower(), CONTAINER_STYLES["rounded"])
