from app.services.figures.design.variants.base import VariantStyle

PIPELINE = VariantStyle(
    name="pipeline",
    node_radius=6,
    container_rx=4,
    show_icons=True,
    group_border_dashed=False,
    node_fill_key="service",
    label_font_size=12,
    extras={"stage_header": True, "connector_caps": "round"},
)
