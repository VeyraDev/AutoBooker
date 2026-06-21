"""Figure rendering pipelines."""

from app.services.figures.render.legacy_svg.flowchart import generate_flowchart
from app.services.figures.render.structured.chart_matplotlib import generate_chart
from app.services.figures.render.image_api import generate_figure_image

__all__ = ["generate_flowchart", "generate_chart", "generate_figure_image"]
