"""SWOT 四象限矩阵渲染。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

_QUADRANTS = (
    ("strengths", "S 优势", "#E8F8F5", "#1E8449", 0, 1),
    ("weaknesses", "W 劣势", "#FDEDEC", "#C0392B", 1, 1),
    ("opportunities", "O 机会", "#EBF5FB", "#2E86C1", 0, 0),
    ("threats", "T 威胁", "#FEF9E7", "#B7950B", 1, 0),
)


def generate_swot_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> tuple[str, Path]:
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.axis("off")
    ax.set_title(title or spec.get("title") or "SWOT 分析", fontsize=14, fontweight="bold", pad=12)

    for key, header, fill, edge, col, row in _QUADRANTS:
        x = col * 1.0 + 0.05
        y = row * 1.0 + 0.05
        rect = Rectangle((x, y), 0.9, 0.9, facecolor=fill, edgecolor=edge, linewidth=1.5)
        ax.add_patch(rect)
        items = spec.get(key) or []
        if isinstance(items, str):
            items = [items]
        lines = [header] + [f"• {str(it)[:20]}" for it in items[:4]]
        ax.text(x + 0.45, y + 0.45, "\n".join(lines), ha="center", va="center", fontsize=9, linespacing=1.3)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight", facecolor="white")
    svg_path = output_path.with_suffix(".svg")
    try:
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    except Exception:
        pass
    plt.close(fig)
    return "swot_matrix", output_path
