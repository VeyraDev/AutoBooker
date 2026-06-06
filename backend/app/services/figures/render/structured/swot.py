"""SWOT 四象限矩阵渲染。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from app.services.figures.render.layout_utils import wrap_text

_QUADRANTS = (
    ("strengths", "S 优势", "#E8F8F5", "#1E8449", 0, 1),
    ("weaknesses", "W 劣势", "#FDEDEC", "#C0392B", 1, 1),
    ("opportunities", "O 机会", "#EBF5FB", "#2E86C1", 0, 0),
    ("threats", "T 威胁", "#FEF9E7", "#B7950B", 1, 0),
)


def _items(spec: dict[str, Any], key: str) -> list[str]:
    items = spec.get(key) or []
    if isinstance(items, str):
        items = [items]
    return [str(it).strip() for it in items if str(it).strip()][:4]


def _cell_text(header: str, items: list[str]) -> str:
    lines = [header]
    for it in items:
        lines.extend("• " + line if idx == 0 else "  " + line for idx, line in enumerate(wrap_text(it, max_units=16, max_lines=2).splitlines()))
    return "\n".join(lines)


def generate_swot_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> tuple[str, Path]:
    max_items = max(len(_items(spec, key)) for key, *_ in _QUADRANTS)
    fig_h = max(6.0, min(8.5, 5.8 + max_items * 0.35))
    fig, ax = plt.subplots(figsize=(8.6, fig_h), dpi=150)
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.axis("off")
    ax.set_title(wrap_text(title or spec.get("title") or "SWOT 分析", max_units=26, max_lines=2), fontsize=14, fontweight="bold", pad=12)

    for key, header, fill, edge, col, row in _QUADRANTS:
        x = col * 1.0 + 0.05
        y = row * 1.0 + 0.05
        rect = Rectangle((x, y), 0.9, 0.9, facecolor=fill, edgecolor=edge, linewidth=1.4)
        ax.add_patch(rect)
        text = _cell_text(header, _items(spec, key))
        ax.text(x + 0.45, y + 0.45, text, ha="center", va="center", fontsize=8.4, linespacing=1.22)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(pad=0.3)
    plt.savefig(output_path, bbox_inches="tight", facecolor="white")
    svg_path = output_path.with_suffix(".svg")
    try:
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    except Exception:
        pass
    plt.close(fig)
    return "swot_matrix", output_path
