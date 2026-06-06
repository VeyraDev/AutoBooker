"""设计 token。"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.figures.design.themes.academic_clean import ACADEMIC_CLEAN
from app.services.figures.design.themes.modern_saas import MODERN_SAAS


@dataclass
class DesignTokens:
    name: str
    background: str
    primary: str
    text: str
    border: str
    card: str
    node_fill: str
    decision_fill: str
    gateway_fill: str
    font_family: str
    font_size: int
    node_radius: int
    node_pad_x: int
    node_pad_y: int
    edge_stroke: str
    edge_width: float
    arrow_size: int
    muted: str = "#64748B"


def tokens_for_theme(theme: str = "modern_saas") -> DesignTokens:
    palette = MODERN_SAAS if theme != "academic_clean" else ACADEMIC_CLEAN
    return DesignTokens(
        name=palette["name"],
        background=palette["background"],
        primary=palette["primary"],
        text=palette["text"],
        border=palette["border"],
        card=palette["card"],
        node_fill=palette.get("service", palette["card"]),
        decision_fill=palette.get("decision", "#FEF3C7"),
        gateway_fill=palette.get("gateway", "#FEF3C7"),
        font_family="Noto Sans CJK SC, sans-serif",
        font_size=13,
        node_radius=8,
        node_pad_x=12,
        node_pad_y=8,
        edge_stroke=palette.get("muted", "#64748B"),
        edge_width=1.5,
        arrow_size=8,
        muted=palette.get("muted", "#64748B"),
    )
