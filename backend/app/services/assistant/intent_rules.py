"""规则优先的意图识别。"""

from __future__ import annotations

import re
from typing import Any

_RULES: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"流程图|流程示意|工作流"), "gen_flowchart", 0.95),
    (re.compile(r"折线图|柱状图|饼图|散点图|热力图|数据图|趋势图"), "gen_chart", 0.92),
    (re.compile(r"架构图|系统架构|模块图|拓扑"), "gen_figure", 0.9),
    (re.compile(r"信息图|infographic", re.I), "gen_figure", 0.88),
    (re.compile(r"概念图|示意图|原理图"), "gen_figure", 0.88),
    (re.compile(r"插画|场景图|配图"), "gen_figure", 0.88),
    (re.compile(r"重新生成|再生成|重做"), "regen_figure", 0.9),
    (re.compile(r"润色"), "polish", 0.9),
    (re.compile(r"扩写|展开"), "expand", 0.9),
    (re.compile(r"缩写|精简|压缩|缩短"), "condense", 0.9),
    (re.compile(r"改写|重写"), "rewrite", 0.88),
    (re.compile(r"风格|语气|口吻"), "style_adjust", 0.85),
    (re.compile(r"术语"), "term_check", 0.85),
]


def match_intent_by_rules(user_text: str) -> dict[str, Any] | None:
    t = (user_text or "").strip()
    if not t:
        return None
    for pat, intent, conf in _RULES:
        if pat.search(t):
            params: dict[str, Any] = {}
            if intent == "gen_figure":
                if pat.pattern.find("架构") >= 0 or "架构" in t:
                    params["sub_kind"] = "architecture"
                elif "信息" in t:
                    params["sub_kind"] = "infographic"
                elif "概念" in t or "原理" in t:
                    params["sub_kind"] = "concept_diagram"
                else:
                    params["sub_kind"] = "illustration"
            return {
                "intent": intent,
                "confidence": conf,
                "extracted_params": params,
                "refined_instruction": t,
            }
    return None
