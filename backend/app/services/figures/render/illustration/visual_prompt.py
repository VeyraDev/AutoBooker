"""插画视觉规划（仅 illustration 路径）。"""

from __future__ import annotations

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.schemas.diagram import PipelineContext, VisualPlan
from app.utils.json_llm import parse_llm_json

_PROMPT = """为书籍插画生成视觉规划 JSON（不负责结构/节点）：
{{
  "layout": "left_to_right|center|full_bleed",
  "style": "academic|modern|minimal",
  "visual_description": "具象画面描述，短段，不要复制原文",
  "must_include": [],
  "must_avoid": ["照片写实", "复杂代码", "可读文字"]
}}
书型风格：{style_type}
描述：{text}
"""


def build_visual_plan(ctx: PipelineContext) -> VisualPlan:
    model = (ctx.model or settings.intent_model).strip()
    if ctx.use_llm and model:
        try:
            out = LLMClient().chat_completion(
                [{"role": "user", "content": _PROMPT.format(
                    style_type=ctx.style_type or "general",
                    text=ctx.normalized_input[:2000],
                )}],
                model=model,
                max_tokens=800,
                temperature=0.3,
            )
            data = parse_llm_json(out)
            if isinstance(data, dict):
                return VisualPlan(
                    layout=str(data.get("layout") or ""),
                    style=str(data.get("style") or ctx.style_type or ""),
                    visual_description=str(data.get("visual_description") or ctx.normalized_input[:400]),
                    must_include=list(data.get("must_include") or [])[:6],
                    must_avoid=list(data.get("must_avoid") or [])[:6],
                )
        except Exception:
            pass
    return VisualPlan(
        style=ctx.style_type or "professional",
        visual_description=ctx.normalized_input[:400],
        must_avoid=["照片写实", "复杂代码"],
    )


def visual_plan_to_prompt(plan: VisualPlan, *, style_type: str = "") -> str:
    parts = [plan.visual_description]
    if plan.layout:
        parts.append(f"布局：{plan.layout}")
    if plan.style or style_type:
        parts.append(f"风格：{plan.style or style_type}")
    if plan.must_include:
        parts.append("须包含：" + "、".join(plan.must_include))
    if plan.must_avoid:
        parts.append("避免：" + "、".join(plan.must_avoid))
    return "\n".join(p for p in parts if p)
