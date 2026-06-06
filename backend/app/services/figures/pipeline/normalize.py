"""输入归一化。"""

from __future__ import annotations

import re

_LAYOUT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"用方框和箭头展示[^，,。；;\n]*", re.I), "用方框和箭头展示"),
    (re.compile(r"用箭头连接以下步骤[^，,。；;\n]*", re.I), "用箭头连接以下步骤"),
    (re.compile(r"用箭头标明顺序[^，,。；;\n]*", re.I), "用箭头标明顺序"),
    (re.compile(r"用箭头连接[^，,。；;\n]*", re.I), "用箭头连接"),
    (re.compile(r"左边是[^，,。；;\n]*右边是[^，,。；;\n]*", re.I), "左右布局说明"),
    (re.compile(r"左侧放[^，,。；;\n]*右侧放[^，,。；;\n]*", re.I), "左右布局说明"),
    (re.compile(r"左侧是[^，,。；;\n]*右侧是[^，,。；;\n]*", re.I), "左右布局说明"),
    (re.compile(r"图中展示[^，,。；;\n]*", re.I), "图中展示"),
    (re.compile(r"画面包含[^，,。；;\n]*", re.I), "画面包含"),
    (re.compile(
        r"(?:用|以|通过)?(?:方框|矩形|圆形|菱形|箭头|连线|节点|图表|图示)[^，,。；;\n]*(?:展示|表示|说明|连接|排列)[^，,。；;\n]*",
        re.I,
    ), "版式说明"),
    (re.compile(r"(?:左边|右边|左侧|右侧|上方|下方|顶部|底部)(?:是|为|放|显示)[^，,。；;\n]*", re.I), "位置说明"),
]


def strip_layout_instructions(text: str) -> tuple[str, list[str]]:
    """剥离版式/布局说明，返回干净文本与剥离片段列表。"""
    instructions: list[str] = []
    cleaned = (text or "").strip()
    for pattern, _ in _LAYOUT_PATTERNS:
        for match in pattern.finditer(cleaned):
            fragment = match.group(0).strip(" ，,。；;")
            if fragment and fragment not in instructions:
                instructions.append(fragment)
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"[，,]{2,}", "，", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ，,。；;")
    return cleaned, instructions


def normalize_figure_input(
    text: str,
    *,
    user_hint: str = "",
    figure_annotation: str = "",
) -> tuple[str, list[str]]:
    """合并输入并剥离版式说明，返回 (normalized_input, layout_instructions)。"""
    parts: list[str] = []
    hint = (user_hint or "").strip()
    ann = (figure_annotation or "").strip()
    raw = (text or "").strip()

    if ann and ann not in raw:
        parts.append(ann)
    if raw:
        parts.append(raw)
    if hint and hint not in "\n".join(parts):
        parts.append(hint)

    merged = "\n".join(p for p in parts if p).strip()
    merged = re.sub(r"\[(?:FIGURE|DIAGRAM|FLOWCHART|CHART|SCREENSHOT):\s*", "", merged, flags=re.I)
    merged = re.sub(r"\]\s*$", "", merged.strip())
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return strip_layout_instructions(merged.strip())


def normalize_figure_input_text(
    text: str,
    *,
    user_hint: str = "",
    figure_annotation: str = "",
) -> str:
    """仅返回归一化文本（兼容旧调用方）。"""
    normalized, _ = normalize_figure_input(text, user_hint=user_hint, figure_annotation=figure_annotation)
    return normalized
