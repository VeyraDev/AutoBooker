"""兼容 shim → figures.render.dispatcher"""

from app.services.figures.render.dispatcher import render_figure as render_figure_asset

__all__ = ["render_figure_asset"]
