from app.services.figures.design.variants.base import VariantStyle

MECHANISM = VariantStyle(
    name="mechanism",
    node_radius=6,
    container_rx=8,
    show_icons=False,
    node_shadow=False,
    node_fill_key="model",
    label_font_size=12,
    edge_width_scale=1.1,
)
