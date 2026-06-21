"""旧三栏架构图渲染兼容层。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from app.services.figures.render.structured.generic_graph import generate_structured_diagram


def generate_rag_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> tuple[str, Path]:
    if spec.get("nodes") and spec.get("edges"):
        return generate_structured_diagram(spec, output_path, title=title or spec.get("title", "系统架构"))

    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 4.5)
    ax.axis("off")
    ax.set_title(title or spec.get("title") or "系统架构", fontsize=13, fontweight="bold")

    boxes = [
        (1.0, 2.2, "用户查询"),
        (3.5, 3.2, "检索器"),
        (3.5, 1.2, "向量库"),
        (6.5, 2.2, "生成模型"),
    ]
    positions = {}
    for x, y, label in boxes:
        w, h = 2.0, 0.7
        box = FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.03", facecolor="#EBF5FB", edgecolor="#2E86C1", linewidth=1.3,
        )
        ax.add_patch(box)
        ax.text(x, y, label, ha="center", va="center", fontsize=10)
        positions[label] = (x, y)

    arrows = [
        ("用户查询", "检索器"),
        ("检索器", "向量库"),
        ("检索器", "生成模型"),
        ("向量库", "生成模型"),
    ]
    for src, dst in arrows:
        x1, y1 = positions[src]
        x2, y2 = positions[dst]
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color="#2E86C1", lw=1.2))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight", facecolor="white")
    svg_path = output_path.with_suffix(".svg")
    try:
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    except Exception:
        pass
    plt.close(fig)
    return "rag_architecture", output_path
