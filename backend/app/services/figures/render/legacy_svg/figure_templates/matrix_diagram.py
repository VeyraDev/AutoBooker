"""注意力矩阵 / 滑动窗口矩阵：matplotlib 程序化绘制。"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
import numpy as np


def _parse_matrix_params(description: str, render_spec: dict | None = None) -> tuple[int, int, str]:
    spec = render_spec or {}
    n = 12
    window = 4
    if spec.get("size"):
        try:
            n = max(4, min(24, int(spec["size"])))
        except (TypeError, ValueError):
            pass
    if spec.get("window"):
        try:
            window = max(2, min(n, int(spec["window"])))
        except (TypeError, ValueError):
            pass
    if not spec.get("size"):
        m = re.search(r"n\s*[×xX]\s*n|(\d+)\s*[×xX]\s*(\d+)", description, re.I)
        if m:
            if m.lastindex and m.lastindex >= 2:
                n = max(4, min(24, int(m.group(1))))
            elif "n" in (m.group(0) or "").lower():
                n = 12
        wm = re.search(r"窗口(?:大小)?[=为]?\s*(\d+)", description)
        if wm:
            window = max(2, min(n, int(wm.group(1))))
    title = str(spec.get("title") or "").strip() or "注意力矩阵示意图"
    if title == "注意力矩阵示意图":
        if "滑动窗口" in description or "sliding" in description.lower():
            title = "滑动窗口注意力示意图"
        elif "完整" in description or "full" in description.lower():
            title = "完整注意力矩阵"
    return n, window, title


def generate_matrix_diagram(
    description: str,
    output_path: Path,
    *,
    render_spec: dict | None = None,
) -> tuple[str, Path]:
    n, window, title = _parse_matrix_params(description, render_spec)
    full = np.ones((n, n))
    band = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if abs(i - j) <= window // 2:
                band[i, j] = 1.0

    fig, axes = plt.subplots(2, 1, figsize=(6, 8), dpi=150)
    fig.suptitle(title, fontsize=14, y=0.98)

    im0 = axes[0].imshow(full, cmap="Blues", vmin=0, vmax=1, aspect="equal")
    axes[0].set_title(f"完整注意力矩阵 ({n}×{n})", fontsize=11)
    axes[0].set_xlabel("Key")
    axes[0].set_ylabel("Query")
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

    im1 = axes[1].imshow(band, cmap="Blues", vmin=0, vmax=1, aspect="equal")
    axes[1].set_title(f"滑动窗口注意力 (窗口={window})", fontsize=11)
    axes[1].set_xlabel("Key")
    axes[1].set_ylabel("Query")
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, bbox_inches="tight", facecolor="white")
    svg_path = output_path.with_suffix(".svg")
    try:
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    except Exception:
        pass
    plt.close(fig)

    spec = f"matrix_diagram n={n} window={window}"
    return spec, output_path
