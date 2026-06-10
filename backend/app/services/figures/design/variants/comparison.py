"""Comparison 四呈现 variant。"""

from __future__ import annotations

from app.services.figures.design.variants.base import VariantStyle

MATRIX = VariantStyle(
    name="matrix",
    node_radius=4,
    container_rx=6,
    show_icons=False,
    node_shadow=False,
    label_font_size=12,
    extras={"template": "matrix", "grid_lines": True, "header_row": True},
)

CARDS = VariantStyle(
    name="cards",
    node_radius=12,
    container_rx=16,
    show_icons=True,
    node_shadow=True,
    node_fill_key="card",
    label_font_size=13,
    extras={"template": "cards", "card_gap": 24, "card_columns": 2},
)

PROS_CONS = VariantStyle(
    name="pros_cons",
    node_radius=8,
    container_rx=10,
    show_icons=False,
    label_font_size=12,
    extras={"template": "pros_cons", "split_axis": "vertical", "pro_color": "#DCFCE7", "con_color": "#FEE2E2"},
)

SCOREBOARD = VariantStyle(
    name="scoreboard",
    node_radius=6,
    container_rx=8,
    show_icons=False,
    label_font_size=12,
    extras={"template": "scoreboard", "rank_badges": True, "score_bars": True},
)

COMPARISON_VARIANTS = {
    "matrix": MATRIX,
    "cards": CARDS,
    "pros_cons": PROS_CONS,
    "scoreboard": SCOREBOARD,
}
