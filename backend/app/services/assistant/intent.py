from __future__ import annotations

import json
import re
from enum import Enum

from app.config import settings
from app.llm.client import LLMClient
from app.services.assistant.context import AssistantContext
from app.services.assistant.intent_rules import match_intent_by_rules


class IntentType(str, Enum):
    polish = "polish"
    rewrite = "rewrite"
    expand = "expand"
    condense = "condense"
    style_adjust = "style_adjust"
    term_check = "term_check"
    gen_flowchart = "gen_flowchart"
    gen_chart = "gen_chart"
    gen_figure = "gen_figure"
    regen_figure = "regen_figure"


INTENT_CLASSIFY_PROMPT = """
根据用户输入和当前上下文，判断用户意图，只返回JSON：
{{
  "intent": "polish|rewrite|expand|condense|style_adjust|term_check|
             gen_flowchart|gen_chart|gen_figure|regen_figure",
  "confidence": 0.0,
  "extracted_params": {{}}
}}

当前上下文：
- 书型：{book_type} / {style_type}
- 当前章节：{chapter_title}
- 光标段落：{cursor_paragraph}
- 选中内容：{selected_text}
- 当前图片描述：{figure_annotation}

用户输入：{user_text}
""".strip()


def _parse_json(text: str) -> dict:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.I)
    if m:
        t = m.group(1).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        t = t[start : end + 1]
    return json.loads(t)


def classify_intent(ctx: AssistantContext, *, model: str | None = None) -> dict:
    if ctx.explicit_intent:
        return {
            "intent": ctx.explicit_intent,
            "confidence": 1.0,
            "extracted_params": {},
            "needs_confirmation": False,
        }
    ruled = match_intent_by_rules(ctx.user_text)
    if ruled and ruled.get("confidence", 0) >= 0.85:
        ruled["needs_confirmation"] = False
        return ruled
    client = LLMClient()
    prompt = INTENT_CLASSIFY_PROMPT.format(
        book_type=ctx.book_type,
        style_type=ctx.style_type,
        chapter_title=ctx.chapter_title,
        cursor_paragraph=(ctx.cursor_paragraph or "")[:300],
        selected_text=(ctx.selected_text or "")[:500],
        figure_annotation=ctx.figure_annotation or "无",
        user_text=ctx.user_text,
    )
    out = client.chat_completion(
        [{"role": "user", "content": prompt}],
        model=model or settings.intent_model,
        max_tokens=300,
        temperature=0.1,
    )
    data = _parse_json(out)
    try:
        conf = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    data["confidence"] = conf
    data["needs_confirmation"] = conf < 0.7
    if data.get("needs_confirmation"):
        data["confirmation_candidates"] = [
            "gen_flowchart",
            "gen_chart",
            "gen_figure",
            "polish",
            "rewrite",
        ]
    return data
