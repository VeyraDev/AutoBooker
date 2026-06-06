"""语义图标绘制（matplotlib patches）。"""

from __future__ import annotations

import matplotlib.patches as mpatches
from matplotlib.axes import Axes

_ICON_COLORS = {
    "gateway": "#D97706",
    "service": "#2563EB",
    "database": "#64748B",
    "queue": "#0891B2",
    "cache": "#7C3AED",
    "user": "#2563EB",
    "client": "#0F172A",
    "model": "#7C3AED",
    "document": "#64748B",
    "api": "#0EA5E9",
    "decision": "#D97706",
    "start": "#64748B",
    "end": "#64748B",
}


def draw_icon(ax: Axes, x: float, y: float, icon: str, *, size: float = 0.12) -> None:
    """在节点左上角绘制小图标。"""
    kind = str(icon or "service").lower()
    color = _ICON_COLORS.get(kind, "#2563EB")
    ix, iy = x - size * 0.35, y + size * 0.25

    if kind == "gateway":
        ax.add_patch(mpatches.FancyBboxPatch((ix, iy), size, size * 0.7, boxstyle="round,pad=0.01", facecolor=color, edgecolor="white", linewidth=0.5))
        ax.plot([ix + size * 0.2, ix + size * 0.8], [iy + size * 0.35, iy + size * 0.35], color="white", linewidth=1.2)
    elif kind == "database":
        ax.add_patch(mpatches.Ellipse((ix + size / 2, iy + size * 0.65), size * 0.9, size * 0.25, facecolor=color, edgecolor="white", linewidth=0.5))
        ax.add_patch(mpatches.Rectangle((ix + size * 0.05, iy), size * 0.9, size * 0.55, facecolor=color, edgecolor="white", linewidth=0.5))
        ax.add_patch(mpatches.Ellipse((ix + size / 2, iy), size * 0.9, size * 0.25, facecolor=color, edgecolor="white", linewidth=0.5))
    elif kind == "queue":
        for i in range(3):
            ax.add_patch(mpatches.Rectangle((ix + i * size * 0.28, iy), size * 0.22, size * 0.55, facecolor=color, edgecolor="white", linewidth=0.4, alpha=0.85 - i * 0.15))
    elif kind == "user":
        ax.add_patch(mpatches.Circle((ix + size / 2, iy + size * 0.55), size * 0.22, facecolor=color, edgecolor="white", linewidth=0.5))
        ax.add_patch(mpatches.Wedge((ix + size / 2, iy + size * 0.15), size * 0.35, 200, 340, facecolor=color, edgecolor="white", linewidth=0.5))
    elif kind == "decision":
        ax.add_patch(mpatches.RegularPolygon((ix + size / 2, iy + size * 0.35), 4, radius=size * 0.35, orientation=0.785, facecolor=color, edgecolor="white", linewidth=0.5))
    elif kind in {"model", "ai"}:
        ax.add_patch(mpatches.Circle((ix + size / 2, iy + size * 0.35), size * 0.35, facecolor=color, edgecolor="white", linewidth=0.5))
        ax.text(ix + size / 2, iy + size * 0.35, "AI", ha="center", va="center", fontsize=5, color="white", fontweight="bold")
    else:
        ax.add_patch(mpatches.RegularPolygon((ix + size / 2, iy + size * 0.35), 6, radius=size * 0.32, facecolor=color, edgecolor="white", linewidth=0.5))
