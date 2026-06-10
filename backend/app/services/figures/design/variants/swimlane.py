from app.services.figures.design.variants.base import VariantStyle

SWIMLANE = VariantStyle(
    name="swimlane",
    node_radius=8,
    container_rx=0,
    show_icons=False,
    group_fill_alpha=0.85,
    group_border_dashed=True,
    node_fill_key="service",
    label_font_size=12,
    extras={"lane_headers": True, "lane_separator": True},
)
