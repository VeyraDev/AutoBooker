"""Component variant 样式配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VariantStyle:
    name: str
    node_radius: int = 8
    container_rx: int = 12
    show_icons: bool = True
    node_shadow: bool = True
    group_fill_alpha: float = 1.0
    group_border_dashed: bool = False
    node_fill_key: str = "service"
    edge_width_scale: float = 1.0
    label_font_size: int = 13
    title_font_size: int = 16
    density_pad: float = 1.0
    extras: dict[str, Any] = field(default_factory=dict)
