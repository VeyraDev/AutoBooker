"""图像接口的分类与布局脚本辅助函数。"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.render.image_api.canvas import canvas_guidance_for_subtype
from app.services.figures.render.image_api.prompt_constraints import (
    CLASSIFIER_AGENT_PROMPT,
    IMAGE_API_SUBTYPES,
    build_layout_agent_prompt,
)

logger = logging.getLogger(__name__)

_VALID_TYPES = set(IMAGE_API_SUBTYPES) | {"chart", "screenshot"}


def _exact_type_or_default(value: str, default: str = "concept_diagram") -> str:
    candidate = _normalize_type_label(value)
    return candidate if candidate in _VALID_TYPES else default

_HEADING_RE = re.compile(
    r"^\s*(主图类|辅图类|不要画成|分类理由|布局规划器应重点处理的风险)\s*[:：]\s*(.*)\s*$"
)
_TYPE_LABEL_ALIASES = {
    "流程图": "process_flow",
    "步骤图": "process_flow",
    "工作流": "process_flow",
    "过程说明": "process_flow",
    "系统架构图": "system_architecture",
    "架构图": "system_architecture",
    "模块架构": "system_architecture",
    "服务拓扑": "system_architecture",
    "机制原理图": "mechanism_diagram",
    "机制图": "mechanism_diagram",
    "原理图": "mechanism_diagram",
    "对比矩阵": "comparison_matrix",
    "对比图": "comparison_matrix",
    "比较矩阵": "comparison_matrix",
    "概念关系图": "concept_diagram",
    "关系图": "concept_diagram",
    "信息图": "infographic",
    "分类图": "taxonomy_map",
    "分类体系": "taxonomy_map",
    "决策树": "decision_tree",
    "决策树图": "decision_tree",
    "时间线": "timeline_roadmap",
    "路线图": "timeline_roadmap",
    "场景插图": "scene_illustration",
    "概念插图": "scene_illustration",
    "数据图表": "chart",
    "图表": "chart",
    "截图": "screenshot",
}


def _clean_value(value: str) -> str:
    text = (value or "").strip()
    if text in {"无", "无。", "none", "None", "N/A", "n/a", "-"}:
        return ""
    return text.strip()


def _normalize_type_label(value: str) -> str:
    raw = _clean_value(value).strip()
    if not raw:
        return ""
    head = re.split(r"[\s,，/、；;]+", raw, maxsplit=1)[0].strip()
    return _TYPE_LABEL_ALIASES.get(head, raw)


def _goal_for_subtype(subtype: str) -> str:
    return {
        "process_flow": "show_workflow",
        "system_architecture": "show_system_architecture",
        "mechanism_diagram": "show_mechanism",
        "comparison_matrix": "show_comparison",
        "concept_diagram": "show_relationship",
        "infographic": "show_summary",
        "taxonomy_map": "show_taxonomy",
        "decision_tree": "show_decision",
        "timeline_roadmap": "show_timeline",
        "scene_illustration": "illustrate_scene",
        "chart": "show_data",
        "screenshot": "show_screenshot",
    }.get(subtype, "show_relationship")


def _route_for_subtype(subtype: str) -> str:
    if subtype == "chart":
        return "chart"
    if subtype == "screenshot":
        return "screenshot_placeholder"
    return "image_api"


def parse_classifier_agent_output(text: str) -> dict[str, Any] | None:
    """Parse the non-JSON Classifier Agent output into internal fields."""
    if not (text or "").strip():
        return None

    fields: dict[str, str] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _HEADING_RE.match(line)
        if match:
            current = match.group(1)
            fields[current] = _clean_value(match.group(2))
            continue
        if current:
            suffix = line.lstrip("-* ").strip()
            if suffix:
                fields[current] = _clean_value((fields.get(current, "") + "\n" + suffix).strip())

    primary = _exact_type_or_default(fields.get("主图类", ""))

    secondary_raw = _normalize_type_label(fields.get("辅图类", ""))
    secondary = secondary_raw if secondary_raw in _VALID_TYPES else ""
    if secondary == primary:
        secondary = ""

    reason = _clean_value(fields.get("分类理由", ""))
    do_not_draw_as = _clean_value(fields.get("不要画成", ""))
    layout_risks = _clean_value(fields.get("布局规划器应重点处理的风险", ""))

    score = 0.92 if primary in IMAGE_API_SUBTYPES else 0.9
    candidate = {"type": primary, "score": score, "reason": reason or "classifier_agent"}
    out = {
        "route": _route_for_subtype(primary),
        "route_confidence": score,
        "confidence": score,
        "goal": _goal_for_subtype(primary),
        "primary_type": primary,
        "secondary_type": secondary,
        "do_not_draw_as": do_not_draw_as,
        "classification_reason": reason,
        "layout_risks": layout_risks,
        "diagram_candidates": [candidate],
        "candidate_diagrams": [candidate],
        "constraints": [],
        "visual_preferences": [],
        "missing_info": [],
        "uncertainties": [],
    }
    return out


def classifier_agent(user_input: str, *, model: str = "", use_llm: bool = True) -> dict[str, Any] | None:
    llm_model = (model or settings.intent_model).strip()
    if not use_llm or not llm_model or llm_model.lower() == "dummy" or not (user_input or "").strip():
        return None
    prompt = CLASSIFIER_AGENT_PROMPT.replace("{user_input}", user_input[:2500])
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出指定标题行文本，不要输出 JSON。"}, {"role": "user", "content": prompt}],
            model=llm_model,
            max_tokens=700,
            temperature=0.0,
        )
        return parse_classifier_agent_output(out)
    except Exception as e:
        logger.warning("figure classifier agent failed: %s", e)
        return None


def build_fallback_layout_script(user_input: str, primary_type: str, *, reason: str = "layout_agent_fallback") -> str:
    st = _exact_type_or_default(primary_type)
    canvas_guidance = canvas_guidance_for_subtype(st, user_input=user_input)
    return f"""【图类确认】
主图类：{st}
辅图类：无
这张图首先应该被读作：{st}
不要画成：无

【可见文字白名单】
图片中只能出现以下文字。
必须逐字复制，不得改写、翻译、扩写、缩写、替换或新增。

标题：
- 无

分组标题：
- 无

节点 / 模块文字：
- {str(user_input or '').strip()}

箭头 / 关系标签：
- 无

注释 / 公式 / 时间点：
- 无

【画布比例与安全边距】
{canvas_guidance}

【文字排版要求】
字体风格：清晰无衬线字体，中文类似 Microsoft YaHei / Noto Sans CJK / Source Han Sans，英文类似 Inter / Arial / Helvetica。
字号层级：标题最大，节点 / 模块文字次之，注释和关系标签较小但仍清晰可读。
文字颜色与背景：深色实心文字，白色或浅色背景，高对比。
中英文混排：保持原始语言、顺序和基线，不翻译、不改写。
禁止的文字效果：不要手写字、涂鸦字、描边字、空心字、阴影字、浮雕字、纹理字、低对比灰字或形似中文的伪字。

【整体版式】
布局规划器未能生成完整布局说明；请按主图类 {st} 生成清晰、完整、不裁切的解释型图示。

【区域与模块摆放】
根据“节点 / 模块文字”中的原始内容安排主要信息单元，不新增可见文字。

【连接关系画法】
只画用户原始内容中明确表达的连接关系，不新增关系标签。

【复杂关系保真】
不得遗漏、合并、改名或翻译用户原始内容中的可见文字。

【布局禁忌】
不得添加用户未提供的标题、英文说明、编号、标签或术语。

【应用的当前图类约束】
使用 {st} 的布局约束。回退原因：{reason}。
""".strip()


def generate_layout_script(
    user_input: str,
    primary_type: str,
    *,
    secondary_type: str = "",
    do_not_draw_as: str = "",
    layout_risks: str = "",
    model: str = "",
    use_llm: bool = True,
) -> tuple[str, bool]:
    """Return (layout_script, used_fallback)."""
    st = _exact_type_or_default(primary_type)
    llm_model = (model or settings.intent_model).strip()
    if not use_llm or not llm_model or llm_model.lower() == "dummy" or not (user_input or "").strip():
        return build_fallback_layout_script(user_input, st, reason="layout_agent_disabled"), True

    prompt = build_layout_agent_prompt(
        user_input,
        st,
        secondary_type=secondary_type,
        do_not_draw_as=do_not_draw_as,
        layout_risks=layout_risks,
    )
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出布局脚本，不要输出 JSON、SVG 或 Mermaid。"}, {"role": "user", "content": prompt}],
            model=llm_model,
            max_tokens=3600,
            temperature=0.0,
        )
        text = (out or "").strip()
        if not text or "{" in text[:20] or "```" in text:
            raise ValueError("布局规划器返回格式无效")
        return text, False
    except Exception as e:
        logger.warning("figure layout planner failed: %s", e)
        return build_fallback_layout_script(user_input, st, reason="layout_agent_error"), True
