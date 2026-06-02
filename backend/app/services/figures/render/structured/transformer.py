"""Transformer 编码器-解码器架构：双塔并列 + 交叉注意力 + 图例。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from app.services.figures.render.svg_export import try_export_matplotlib_svg

_LEGEND = (
    ("#EBF5FB", "编码器子层"),
    ("#E8F8F5", "解码器子层"),
    ("#2E86C1", "交叉注意力"),
)


def _parse_n_blocks(description: str, spec: dict[str, Any] | None) -> tuple[int, int]:
    spec = spec or {}
    enc = spec.get("encoder_layers")
    dec = spec.get("decoder_layers")
    if enc is not None and dec is not None:
        try:
            return max(1, min(12, int(enc))), max(1, min(12, int(dec)))
        except (TypeError, ValueError):
            pass
    m = re.search(r"(\d+)\s*层", description)
    if m:
        n = max(1, min(12, int(m.group(1))))
        return n, n
    m = re.search(r"[Nn]\s*(?:个|×|x|块|层)?\s*(\d+)?", description)
    if m and m.group(1):
        n = max(1, min(6, int(m.group(1))))
        return n, n
    return 3, 3


def _draw_block(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    *,
    face: str = "#EBF5FB",
    edge: str = "#2E86C1",
) -> None:
    rect = mpatches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02",
        linewidth=1.2,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=8, wrap=True)


def _draw_legend(ax) -> None:
    y = 0.08
    for i, (color, label) in enumerate(_LEGEND):
        x = 0.15 + i * 2.8
        if label == "交叉注意力":
            ax.annotate(
                "",
                xy=(x + 0.35, y + 0.04),
                xytext=(x, y + 0.04),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.5),
            )
            ax.text(x + 0.55, y + 0.04, label, va="center", fontsize=8)
        else:
            patch = mpatches.FancyBboxPatch(
                (x, y),
                0.28,
                0.12,
                boxstyle="round,pad=0.01",
                facecolor=color,
                edgecolor="#555",
                linewidth=0.8,
            )
            ax.add_patch(patch)
            ax.text(x + 0.38, y + 0.06, label, va="center", fontsize=8)


def generate_transformer_architecture(
    description: str,
    output_path: Path,
    *,
    render_spec: dict[str, Any] | None = None,
    title: str = "",
) -> tuple[str, Path]:
    spec = render_spec or {}
    n_enc, n_dec = _parse_n_blocks(description, spec)
    chart_title = title or str(spec.get("title") or "Transformer 编码器-解码器架构")

    fig, ax = plt.subplots(figsize=(10.5, 7.5), dpi=150)
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title(chart_title, fontsize=13, pad=12, fontweight="bold")

    enc_x, dec_x = 0.6, 5.8
    w, h = 3.4, 0.52
    gap = 0.10
    enc_color, dec_color = "#EBF5FB", "#E8F8F5"

    ax.text(enc_x + w / 2, 9.55, "编码器 (Encoder)", ha="center", fontsize=11, fontweight="bold")
    ax.text(dec_x + w / 2, 9.55, "解码器 (Decoder)", ha="center", fontsize=11, fontweight="bold")

    y = 8.85
    _draw_block(ax, enc_x, y, w, h, "输入嵌入 + 位置编码", face=enc_color)
    _draw_block(ax, dec_x, y, w, h, "输出嵌入 + 位置编码", face=dec_color)
    y -= h + gap + 0.18

    enc_layer_tops: list[float] = []
    enc_bottom = y
    for i in range(n_enc):
        block_y = y - i * (h * 2.15 + gap)
        _draw_block(ax, enc_x, block_y, w, h, f"多头自注意力 ×{n_enc - i}", face=enc_color)
        ffn_y = block_y - h - 0.07
        _draw_block(ax, enc_x, ffn_y, w, h, "前馈网络 (FFN)", face=enc_color)
        ax.annotate(
            "",
            xy=(enc_x + w / 2, ffn_y + h),
            xytext=(enc_x + w / 2, block_y),
            arrowprops=dict(arrowstyle="->", color="#555"),
        )
        enc_layer_tops.append(block_y + h / 2)
        if i < n_enc - 1:
            ax.annotate(
                "",
                xy=(enc_x + w / 2, ffn_y - 0.04),
                xytext=(enc_x + w / 2, ffn_y - h - gap - 0.06),
                arrowprops=dict(arrowstyle="->", color="#555"),
            )
        enc_bottom = ffn_y

    dec_cross_y: list[float] = []
    dec_y = y
    for i in range(n_dec):
        by = dec_y - i * (h * 2.95 + gap)
        _draw_block(ax, dec_x, by, w, h, "掩码多头自注意力", face=dec_color)
        cross_y = by - h - 0.07
        _draw_block(ax, dec_x, cross_y, w, h, "交叉注意力 (Cross-Attn)", face=dec_color)
        ffn_y = cross_y - h - 0.07
        _draw_block(ax, dec_x, ffn_y, w, h, "前馈网络 (FFN)", face=dec_color)
        dec_cross_y.append(cross_y + h / 2)
        if i < n_dec - 1:
            ax.annotate(
                "",
                xy=(dec_x + w / 2, ffn_y - 0.04),
                xytext=(dec_x + w / 2, ffn_y - h - gap - 0.08),
                arrowprops=dict(arrowstyle="->", color="#555"),
            )

    ax.text(enc_x + w / 2, enc_bottom - 0.42, "编码表示", ha="center", fontsize=9)
    ax.text(dec_x + w / 2, 0.95, "输出概率 (Softmax)", ha="center", fontsize=9)

    for i, cy in enumerate(dec_cross_y):
        src_idx = min(len(enc_layer_tops) - 1, i) if enc_layer_tops else 0
        src_y = enc_layer_tops[src_idx] if enc_layer_tops else enc_bottom
        ax.annotate(
            "",
            xy=(dec_x, cy),
            xytext=(enc_x + w, src_y),
            arrowprops=dict(arrowstyle="-|>", color="#2E86C1", lw=1.2, connectionstyle="arc3,rad=0.08"),
        )

    ax.text(5.2, 0.55, "各子层均含残差连接 + 层归一化（图中省略）", ha="center", fontsize=8, color="#666")
    _draw_legend(ax)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight", facecolor="white")
    try_export_matplotlib_svg(fig, output_path.with_suffix(".svg"))
    plt.close(fig)
    return f"transformer_arch enc={n_enc} dec={n_dec}", output_path
