"""CHART pipeline: LLM → JSON spec → matplotlib PNG."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
import numpy as np

from app.llm.client import LLMClient
from app.prompts.chart import CHART_PARSE_PROMPT


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
        temperature=0.35,
    )
    return _extract_json(out)


def render_chart(chart_spec: dict[str, Any], output_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    chart_type = chart_spec.get("chart_type", "line")

    if chart_type == "line":
        for series in chart_spec.get("series", []):
            xs = [float(p[0]) for p in series.get("data", [])]
            ys = [float(p[1]) for p in series.get("data", [])]
            ax.plot(xs, ys, label=series.get("name", ""), linewidth=2)
        if chart_spec.get("series"):
            ax.legend()

    elif chart_type == "bar":
        series_list = chart_spec.get("series", [])
        if len(series_list) == 1:
            labels = [str(p[0]) for p in series_list[0].get("data", [])]
            values = [float(p[1]) for p in series_list[0].get("data", [])]
            ax.bar(labels, values)
        else:
            # grouped bar — use first series labels
            labels = [str(p[0]) for p in series_list[0].get("data", [])]
            x = np.arange(len(labels))
            width = 0.8 / max(len(series_list), 1)
            for i, series in enumerate(series_list):
                values = [float(p[1]) for p in series.get("data", [])]
                ax.bar(x + i * width, values, width, label=series.get("name", ""))
            ax.set_xticks(x + width * (len(series_list) - 1) / 2)
            ax.set_xticklabels(labels)
            ax.legend()

    elif chart_type == "scatter":
        for series in chart_spec.get("series", []):
            xs = [float(p[0]) for p in series.get("data", [])]
            ys = [float(p[1]) for p in series.get("data", [])]
            ax.scatter(xs, ys, label=series.get("name", ""))
        if chart_spec.get("series"):
            ax.legend()

    elif chart_type == "heatmap":
        series = chart_spec.get("series", [{}])[0]
        data = series.get("data", [])
        if data and isinstance(data[0], list):
            mat = np.array(data, dtype=float)
            im = ax.imshow(mat, aspect="auto", cmap="Blues")
            plt.colorbar(im, ax=ax)
        else:
            ax.text(0.5, 0.5, "无热力图数据", ha="center", va="center", transform=ax.transAxes)

    elif chart_type == "pie":
        series = chart_spec.get("series", [{}])[0]
        labels = [str(p[0]) for p in series.get("data", [])]
        values = [float(p[1]) for p in series.get("data", [])]
        ax.pie(values, labels=labels, autopct="%1.1f%%")

    ax.set_title(chart_spec.get("title", ""), fontsize=14)
    ax.set_xlabel(chart_spec.get("x_label", ""))
    ax.set_ylabel(chart_spec.get("y_label", ""))

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

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
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
    if render_spec and render_spec.get("values"):
        spec = dict(render_spec)
    else:
        desc = description
        if chart_type_hint:
            desc = f"图表类型：{chart_type_hint}\n{description}"
        spec = parse_chart_spec(desc, model=model)
    if chart_type_hint and spec.get("chart_type") in (None, ""):
        spec["chart_type"] = chart_type_hint
    spec_json = json.dumps(spec, ensure_ascii=False)
    png = render_chart(spec, output_path)
    return spec_json, png
