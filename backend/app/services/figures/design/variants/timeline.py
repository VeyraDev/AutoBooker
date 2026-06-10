from app.services.figures.design.variants.base import VariantStyle

TIMELINE = VariantStyle(
    name="timeline",
    node_radius=20,
    container_rx=20,
    show_icons=False,
    node_shadow=True,
    node_fill_key="card",
    label_font_size=12,
    extras={"axis_line": True, "milestone_dot": True},
)
