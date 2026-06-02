"""注意力矩阵解析。"""

from __future__ import annotations

import re

from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext


def parse_attention_matrix(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    t = ctx.normalized_input
    n, window = 12, 4
    m = re.search(r"(\d+)\s*[×xX]\s*(\d+)", t)
    if m:
        n = max(4, min(24, int(m.group(1))))
    wm = re.search(r"窗口(?:大小)?[=为]?\s*(\d+)", t)
    if wm:
        window = max(2, min(n, int(wm.group(1))))
    title = intent.title or "注意力矩阵示意图"
    if "滑动窗口" in t:
        title = "滑动窗口注意力示意图"
    return ParsedDiagram(
        {
            "title": title,
            "size": n,
            "window": window,
            "show_full": True,
            "show_window": True,
        },
        "rules_matrix",
    )
