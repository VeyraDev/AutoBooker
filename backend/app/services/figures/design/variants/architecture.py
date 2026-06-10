from app.services.figures.design.variants.base import VariantStyle

ARCHITECTURE = VariantStyle(
    name="architecture",
    node_radius=8,
    container_rx=14,
    show_icons=False,
    group_fill_alpha=0.92,
    node_fill_key="service",
    label_font_size=12,
    density_pad=1.1,
)
