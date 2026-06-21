"""旧双栈机制结构图渲染兼容层。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from app.services.figures.render.layout_utils import wrap_text
from app.services.figures.render.svg_export import try_export_matplotlib_svg

_LEGEND = (
    ("#EBF5FB", "编码器路径"),
    ("#E8F8F5", "解码器路径"),
    ("#2E86C1", "交叉注意力"),
)

_LAYER_LABELS = {
    "multi_head_self_attention": "多头自注意力",
    "masked_multi_head_self_attention": "掩码多头自注意力",
    "self_attention": "自注意力",
    "cross_attention": "交叉注意力",
    "feed_forward": "前馈网络",
    "ffn": "前馈网络",
    "add_norm": "残差连接 + 层归一化",
    "layer_norm": "层归一化",
    "residual": "残差连接",
}


def _parse_n_blocks(description: str, spec: dict[str, Any] | None) -> tuple[int, int]:
    spec = spec or {}
    enc = spec.get("encoder_layers")
    dec = spec.get("decoder_layers")
    if enc is not None and dec is not None:
        try:
            return max(1, min(96, int(enc))), max(1, min(96, int(dec)))
        except (TypeError, ValueError):
            pass
    m = re.search(r"(\d+)\s*层", description)
    if m:
        n = max(1, min(96, int(m.group(1))))
        return n, n
    return 6, 6


def _layer_sequence(spec: dict[str, Any], side: str, fallback: list[str]) -> list[str]:
    value = spec.get(side)
    if isinstance(value, dict):
        value = value.get("layers") or value.get("modules")
    if not isinstance(value, list):
        return fallback
    out = [str(x).strip() for x in value if str(x).strip()]
    return out or fallback


def _sequence_label(prefix: str, count: int, layers: list[str]) -> str:
    labels = [_LAYER_LABELS.get(layer, layer) for layer in layers]
    compact: list[str] = []
    for label in labels:
        if label not in compact:
            compact.append(label)
    return f"{prefix} ×{count}\n" + "\n".join(compact[:4])


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
    bold: bool = False,
) -> None:
    rect = mpatches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.025,rounding_size=0.05",
        linewidth=1.2,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h / 2, wrap_text(label, max_units=14, max_lines=2), ha="center", va="center", fontsize=8.8, fontweight="bold" if bold else "normal", linespacing=1.18)


def _draw_stack(ax, x: float, y: float, w: float, h: float, label: str, *, face: str, edge: str) -> None:
    # A folded repeated layer avoids unreadable overlap when N=6/12/32.
    for dx, dy, alpha in [(0.12, -0.12, 0.32), (0.06, -0.06, 0.55), (0, 0, 1.0)]:
        rect = mpatches.FancyBboxPatch(
            (x + dx, y + dy),
            w,
            h,
            boxstyle="round,pad=0.025,rounding_size=0.05",
            linewidth=1.1,
            edgecolor=edge,
            facecolor=face,
            alpha=alpha,
        )
        ax.add_patch(rect)
    ax.text(x + w / 2, y + h / 2, wrap_text(label, max_units=18, max_lines=3), ha="center", va="center", fontsize=8.6, linespacing=1.18)


def _draw_legend(ax) -> None:
    y = 0.18
    for i, (color, label) in enumerate(_LEGEND):
        x = 0.9 + i * 3.0
        if label == "交叉注意力":
            ax.annotate("", xy=(x + 0.42, y + 0.06), xytext=(x, y + 0.06), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.5))
            ax.text(x + 0.58, y + 0.06, label, va="center", fontsize=8)
        else:
            patch = mpatches.FancyBboxPatch((x, y), 0.30, 0.14, boxstyle="round,pad=0.01", facecolor=color, edgecolor="#555", linewidth=0.8)
            ax.add_patch(patch)
            ax.text(x + 0.42, y + 0.07, label, va="center", fontsize=8)


def generate_transformer_architecture(
    description: str,
    output_path: Path,
    *,
    render_spec: dict[str, Any] | None = None,
    title: str = "",
) -> tuple[str, Path]:
    spec = render_spec or {}
    n_enc, n_dec = _parse_n_blocks(description, spec)
    chart_title = title or str(spec.get("title") or "双栈机制结构图")
    enc_layers = _layer_sequence(
        spec,
        "encoder",
        ["multi_head_self_attention", "add_norm", "feed_forward", "add_norm"],
    )
    dec_layers = _layer_sequence(
        spec,
        "decoder",
        ["masked_multi_head_self_attention", "add_norm", "cross_attention", "add_norm", "feed_forward", "add_norm"],
    )

    fig, ax = plt.subplots(figsize=(10.5, 6.4), dpi=150)
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 8.0)
    ax.axis("off")
    ax.set_title(wrap_text(chart_title, max_units=28, max_lines=2), fontsize=13, pad=10, fontweight="bold")

    enc_x, dec_x = 0.85, 6.05
    w, h = 3.35, 0.72
    enc_color, dec_color = "#EBF5FB", "#E8F8F5"

    ax.text(enc_x + w / 2, 7.25, "编码器 Encoder", ha="center", fontsize=11, fontweight="bold")
    ax.text(dec_x + w / 2, 7.25, "解码器 Decoder", ha="center", fontsize=11, fontweight="bold")

    _draw_block(ax, enc_x, 6.45, w, h, "输入嵌入 + 位置编码", face=enc_color, bold=True)
    _draw_stack(ax, enc_x, 4.75, w, 1.15, _sequence_label("编码器层", n_enc, enc_layers), face=enc_color, edge="#2E86C1")
    _draw_block(ax, enc_x, 3.35, w, h, "编码表示", face="#FFFFFF")

    _draw_block(ax, dec_x, 6.45, w, h, "输出嵌入 + 位置编码", face=dec_color, edge="#27AE60", bold=True)
    _draw_stack(ax, dec_x, 4.55, w, 1.38, _sequence_label("解码器层", n_dec, dec_layers), face=dec_color, edge="#27AE60")
    _draw_block(ax, dec_x, 3.15, w, h, "线性层 + Softmax", face="#FFFFFF", edge="#27AE60")

    # Main arrows
    for x in (enc_x + w / 2, dec_x + w / 2):
        ax.annotate("", xy=(x, 5.93), xytext=(x, 6.45), arrowprops=dict(arrowstyle="->", color="#555", lw=1.0))
        ax.annotate("", xy=(x, 4.05), xytext=(x, 4.75), arrowprops=dict(arrowstyle="->", color="#555", lw=1.0))

    ax.annotate(
        "",
        xy=(dec_x, 5.20),
        xytext=(enc_x + w, 3.70),
        arrowprops=dict(arrowstyle="-|>", color="#2E86C1", lw=1.5, connectionstyle="arc3,rad=-0.10"),
    )
    ax.text(5.28, 4.35, "交叉注意力读取编码表示", ha="center", fontsize=8.2, color="#2E86C1")

    ax.text(5.25, 1.0, "注：重复层采用折叠表达，避免在书稿内页中因 N 层展开导致重叠。", ha="center", fontsize=8, color="#666")
    _draw_legend(ax)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(pad=0.25)
    plt.savefig(output_path, bbox_inches="tight", facecolor="white")
    try_export_matplotlib_svg(fig, output_path.with_suffix(".svg"))
    plt.close(fig)
    return f"transformer_arch folded enc={n_enc} dec={n_dec}", output_path
