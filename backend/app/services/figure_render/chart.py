"""CHART pipeline: LLM → JSON spec → matplotlib PNG.

Data charts must render from explicit numeric data. This module accepts both the
legacy {series:[...]} schema and the V2 parser schema {labels:[...], values:[...]}.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
import numpy as np

from app.llm.client import LLMClient
from app.prompts.chart import CHART_PARSE_PROMPT
from app.services.figures.render.layout_utils import wrap_text


def _extract_json(text: str) -> dict[str, Any]:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.I)
    if m:
        t = m.group(1).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        t = t[start : end + 1]
    return json.loads(t)


def parse_chart_spec(description: str, *, model: str) -> dict[str, Any]:
    client = LLMClient()
    out = client.chat_completion(
        [
            {"role": "system", "content": "只输出合法 JSON，不要解释。"},
            {"role": "user", "content": CHART_PARSE_PROMPT.format(description=description)},
        ],
        model=model,
        max_tokens=4096,
        temperature=0.25,
    )
    return _extract_json(out)


def _as_float(x: Any) -> float | None:
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("%", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _normalize_chart_spec(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize V1/V2 chart specs into the renderer's series schema."""
    spec = dict(raw or {})
    chart_type = str(spec.get("chart_type") or spec.get("type") or "bar").lower()
    if chart_type not in {"line", "bar", "scatter", "heatmap", "pie"}:
        chart_type = "bar"

    # V2 schema: labels + values, optionally list[list] for grouped series.
    labels = spec.get("labels") or spec.get("x") or []
    values = spec.get("values") or spec.get("y") or []
    if not spec.get("series") and isinstance(labels, list) and isinstance(values, list) and labels and values:
        if values and all(isinstance(v, list) for v in values):
            names = spec.get("series_names") or [f"系列 {i + 1}" for i in range(len(values))]
            series = []
            for i, row in enumerate(values):
                data = []
                for label, val in zip(labels, row):
                    fv = _as_float(val)
                    if fv is not None:
                        data.append([str(label), fv])
                if data:
                    series.append({"name": str(names[i] if i < len(names) else f"系列 {i + 1}"), "data": data})
            spec["series"] = series
        else:
            data = []
            for label, val in zip(labels, values):
                fv = _as_float(val)
                if fv is not None:
                    data.append([str(label), fv])
            if data:
                spec["series"] = [{"name": str(spec.get("series_name") or spec.get("title") or "数据"), "data": data}]

    spec["chart_type"] = chart_type
    spec.setdefault("title", "")
    spec.setdefault("x_label", spec.get("x_label") or spec.get("xlabel") or "")
    spec.setdefault("y_label", spec.get("y_label") or spec.get("ylabel") or "")
    return spec


def _figure_size(spec: dict[str, Any]) -> tuple[float, float]:
    series = spec.get("series") or []
    max_points = max((len(s.get("data") or []) for s in series if isinstance(s, dict)), default=0)
    n_series = len(series)
    w = max(7.2, min(12.5, 6.8 + max_points * 0.32 + n_series * 0.25))
    h = max(4.6, min(7.2, 4.6 + n_series * 0.18))
    return w, h


def render_chart(chart_spec: dict[str, Any], output_path: Path) -> Path:
    chart_spec = _normalize_chart_spec(chart_spec)
    fig_w, fig_h = _figure_size(chart_spec)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    chart_type = chart_spec.get("chart_type", "line")
    series_list = chart_spec.get("series") or []

    if chart_type == "line":
        for series in series_list:
            points = series.get("data", []) if isinstance(series, dict) else []
            xs = [p[0] for p in points]
            ys = [_as_float(p[1]) for p in points]
            pairs = [(x, y) for x, y in zip(xs, ys) if y is not None]
            if not pairs:
                continue
            ax.plot([p[0] for p in pairs], [p[1] for p in pairs], label=series.get("name", ""), linewidth=2, marker="o")
        if len(series_list) > 1:
            ax.legend(frameon=False)

    elif chart_type == "bar":
        if len(series_list) == 1:
            points = series_list[0].get("data", [])
            labels = [str(p[0]) for p in points]
            values = [_as_float(p[1]) for p in points]
            pairs = [(l, v) for l, v in zip(labels, values) if v is not None]
            ax.bar([p[0] for p in pairs], [p[1] for p in pairs])
        else:
            labels = [str(p[0]) for p in series_list[0].get("data", [])]
            x = np.arange(len(labels))
            width = 0.8 / max(len(series_list), 1)
            for i, series in enumerate(series_list):
                values = [_as_float(p[1]) for p in series.get("data", [])]
                values = [0.0 if v is None else v for v in values]
                ax.bar(x + i * width, values[: len(labels)], width, label=series.get("name", ""))
            ax.set_xticks(x + width * (len(series_list) - 1) / 2)
            ax.set_xticklabels(labels)
            ax.legend(frameon=False)

    elif chart_type == "scatter":
        for series in series_list:
            xs = [_as_float(p[0]) for p in series.get("data", [])]
            ys = [_as_float(p[1]) for p in series.get("data", [])]
            pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
            ax.scatter([p[0] for p in pairs], [p[1] for p in pairs], label=series.get("name", ""))
        if len(series_list) > 1:
            ax.legend(frameon=False)

    elif chart_type == "heatmap":
        series = series_list[0] if series_list else {}
        data = series.get("data", []) if isinstance(series, dict) else []
        if data and isinstance(data[0], list):
            mat = np.array(data, dtype=float)
            im = ax.imshow(mat, aspect="auto")
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        else:
            ax.text(0.5, 0.5, "无热力图数据", ha="center", va="center", transform=ax.transAxes)

    elif chart_type == "pie":
        series = series_list[0] if series_list else {}
        points = series.get("data", []) if isinstance(series, dict) else []
        labels = [str(p[0]) for p in points]
        values = [_as_float(p[1]) for p in points]
        pairs = [(l, v) for l, v in zip(labels, values) if v is not None]
        if pairs:
            ax.pie([p[1] for p in pairs], labels=[p[0] for p in pairs], autopct="%1.1f%%")

    if not series_list and chart_type != "heatmap":
        ax.text(0.5, 0.5, "缺少可绘制数据", ha="center", va="center", transform=ax.transAxes)

    ax.set_title(wrap_text(chart_spec.get("title", ""), max_units=28, max_lines=2), fontsize=13, pad=10)
    ax.set_xlabel(chart_spec.get("x_label", ""))
    ax.set_ylabel(chart_spec.get("y_label", ""))
    if chart_type in {"bar", "line"}:
        ax.tick_params(axis="x", rotation=25 if len(ax.get_xticklabels()) > 5 else 0)
    ax.grid(True, axis="y", alpha=0.18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    if chart_spec.get("is_illustrative"):
        ax.text(
            0.99,
            0.01,
            "示意数据，请替换为真实数据",
            transform=ax.transAxes,
            fontsize=8,
            color="gray",
            ha="right",
            va="bottom",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    svg_path = output_path.with_suffix(".svg")
    try:
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    except Exception:
        pass
    plt.close(fig)
    return output_path


def generate_chart(
    description: str,
    output_path: Path,
    *,
    model: str,
    chart_type_hint: str | None = None,
    render_spec: dict | None = None,
) -> tuple[str, Path]:
    if render_spec and (render_spec.get("values") or render_spec.get("series")):
        spec = _normalize_chart_spec(render_spec)
    else:
        desc = description
        if chart_type_hint:
            desc = f"图表类型：{chart_type_hint}\n{description}"
        spec = _normalize_chart_spec(parse_chart_spec(desc, model=model))
    if chart_type_hint and spec.get("chart_type") in (None, ""):
        spec["chart_type"] = chart_type_hint
    spec_json = json.dumps(spec, ensure_ascii=False)
    png = render_chart(spec, output_path)
    return spec_json, png
