"""把自然语言图示需求编译为通用 DiagramSpec。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.render.html_template.schema import STYLE_PROFILE, TEMPLATE_IDS, limits_as_json

logger = logging.getLogger(__name__)

LLM_SPEC_SYSTEM_PROMPT = f"""你是图示规格编译器。
你的任务是把用户的中文或中英文图示需求转换为可渲染的 DiagramSpec JSON。

核心规则：
1. 只输出 JSON，不要输出 Markdown、解释或代码块。
2. template_id 必须来自模板枚举，不能自创模板。
3. 用户显式布局要求优先；没有显式要求时，根据内容结构、节点数量、文字密度选择模板。
4. 你不输出坐标，不输出样式代码，不输出矢量图代码。
5. 控制文字密度：标题短，bullet 每条不超过 26 个中文字符；每个模块 2-3 条 bullet。
6. 内容过载时不要硬塞：选择 grouped_infographic，或输出 needs_clarification。
7. 不要添加与主题无关的“开始/结束/反馈”等模板语义。

模板枚举与容量：
{json.dumps(limits_as_json(), ensure_ascii=False, indent=2)}

通用字段：
chart_type, template_id, title, subtitle, language, style_profile, note。

可用 template_id：
{", ".join(TEMPLATE_IDS)}

需要追问时输出：
{{"needs_clarification": true, "questions": ["问题1", "问题2"], "reason": "为什么不能直接画"}}
"""

_PUNCT_RE = re.compile(r"[。.!！?？]\s*")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_GENERIC_WORDS = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛")


def compile_diagram_spec(
    user_prompt: str,
    *,
    subtype: str = "",
    model: str = "",
    use_llm: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """返回 ``(DiagramSpec, diagnostics)``。"""
    st = canonical_subtype(subtype)
    text = str(user_prompt or "").strip()
    if use_llm and text:
        llm_model = (model or settings.intent_model).strip()
        if llm_model and llm_model.lower() != "dummy":
            spec = _compile_with_llm(text, st, llm_model)
            if spec:
                return spec, {"source": "llm", "compiler_fallback": False}
    return compile_prompt_heuristic(text, subtype=st), {"source": "heuristic", "compiler_fallback": True}


def _compile_with_llm(user_prompt: str, subtype: str, model: str) -> dict[str, Any] | None:
    prompt = f"""主图类：{subtype or "未指定"}

用户需求：
{user_prompt[:4000]}

请输出 DiagramSpec JSON。"""
    try:
        raw = LLMClient().chat_completion(
            [{"role": "system", "content": LLM_SPEC_SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=2400,
            temperature=0.0,
        )
        return _parse_json_object(raw)
    except Exception as exc:
        logger.warning("DiagramSpec compiler LLM failed: %s", exc)
        return None


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def compile_prompt_heuristic(prompt: str, *, subtype: str = "") -> dict[str, Any]:
    text = prompt.strip()
    if not _has_enough_structure(text):
        return {
            "needs_clarification": True,
            "questions": [
                "请选择图类：流程、架构、对比、时间线、决策树、分类、概念关系或信息图。",
                "请给出 3-8 个模块、阶段、维度、类别或明确它们之间的关系。",
            ],
            "reason": "输入缺少可排版结构。",
        }

    st = canonical_subtype(subtype)
    if st == "timeline_roadmap" or _contains_any(text, ["时间线", "演进", "路线图", "年份"]) or _YEAR_RE.search(text):
        return _compile_timeline(text)
    if st == "comparison_matrix" or _contains_any(text, ["对比", "比较", "维度", "vs", "VS"]):
        return _compile_comparison(text)
    if st == "decision_tree" or _contains_any(text, ["决策树", "判断", "分支", "选择", "是否"]):
        return _compile_decision(text)
    if st == "taxonomy_map" or _contains_any(text, ["分类", "根节点", "一级分为", "分为", "下有"]):
        return _compile_taxonomy(text)
    if st == "mechanism_diagram" or _contains_any(text, ["机制", "原理", "矩阵", "向量", "公式", "变量", "权重", "输入", "输出"]):
        return _compile_mechanism(text)
    if st == "system_architecture" or _contains_any(text, ["架构", "模块", "系统", "服务", "数据库", "队列", "网关", "缓存", "基础设施"]):
        return _compile_architecture(text)
    if st == "concept_diagram" or _contains_any(text, ["关系", "关联", "影响", "依赖", "映射", "组成"]):
        return _compile_concept(text)
    if st == "process_flow" or _contains_any(text, ["流程", "管线", "阶段", "步骤", "依次", "经过", "箭头", "→", "->"]):
        return _compile_flow(text)
    return _compile_infographic(text)


def _has_enough_structure(text: str) -> bool:
    if len(text) < 8:
        return False
    return _contains_any(
        text,
        ["包含", "分为", "下有", "对比", "流程", "架构", "时间线", "决策", "步骤", "阶段", "→", "->", "、"],
    )


def _contains_any(text: str, words: list[str]) -> bool:
    lower = text.lower()
    return any(w.lower() in lower for w in words)


def _between(text: str, start: str, end_pattern: str = r"[。.]|，每|，用|，箭头|，从|$") -> str:
    idx = text.find(start)
    if idx < 0:
        return ""
    sub = text[idx + len(start) :]
    match = re.search(end_pattern, sub)
    return sub[: match.start()].strip() if match else sub.strip()


def _split_list(value: str) -> list[str]:
    text = str(value or "")
    text = text.replace("→", "、").replace("->", "、").replace("=>", "、")
    text = re.sub(r"[，,；;]", "、", text)
    out: list[str] = []
    for item in text.split("、"):
        clean = item.strip().strip("：:。.")
        clean = re.sub(r"^(和|以及|并|最后|最终|先|再|然后)", "", clean).strip()
        clean = re.sub(r"(共\d+个步骤|每个步骤.*|用方框表示|箭头连接)$", "", clean).strip()
        if clean:
            out.append(clean)
    return list(dict.fromkeys(out))


def _title_from_prompt(text: str, fallback: str) -> str:
    head = _PUNCT_RE.split(text, maxsplit=1)[0]
    head = re.split(r"[，,；;：:]", head, maxsplit=1)[0].strip()
    head = re.sub(r"^(请|生成|绘制|画一张|一张)", "", head).strip(" ：:，,。")
    return head[:32] if head else fallback


def _bullets_for(name: str, count: int = 3) -> list[str]:
    clean = str(name or "").strip() or "该模块"
    return [
        f"明确{clean}的输入",
        f"完成{clean}的核心处理",
        f"输出{clean}的阶段结果",
    ][:count]


def _stage(title: str, i: int, total: int) -> dict[str, Any]:
    return {
        "title": title,
        "icon": "step",
        "bullets": _bullets_for(title, 3),
        "io": [f"输入：{'原始信息' if i == 0 else '上一步结果'}", f"输出：{'最终结果' if i == total - 1 else '阶段产物'}"],
        "connector": "进入\n下一步" if i < total - 1 else "",
    }


def _extract_flow_items(text: str) -> list[str]:
    if "→" in text or "->" in text:
        tail = re.split(r"[：:]", text, maxsplit=1)[-1]
        return _split_list(tail)

    match = re.search(r"从(.+?)开始[，,]?\s*经过(.+?)[，,]?\s*最终(.+?)(?:[，,。.]|$)", text)
    if match:
        return [match.group(1).strip(), *_split_list(match.group(2)), match.group(3).strip()]

    list_text = _between(text, "依次为") or _between(text, "步骤依次为") or _between(text, "包含") or _between(text, "包括")
    items = _split_list(list_text)
    if len(items) >= 2:
        return items
    return []


def _compile_flow(text: str) -> dict[str, Any]:
    items = _extract_flow_items(text) or list(_GENERIC_WORDS[:3])
    title = _title_from_prompt(text, "流程示意图")
    template_id = "horizontal_stage_cards" if len(items) <= 4 else "snake_cards"
    stages = [_stage(name, i, len(items)) for i, name in enumerate(items)]
    if template_id == "horizontal_stage_cards":
        return {
            "chart_type": "process_flow",
            "template_id": template_id,
            "title": title,
            "subtitle": "按步骤顺序阅读",
            "language": "zh-CN",
            "style_profile": STYLE_PROFILE,
            "stages": stages,
            "note": "主路径保持清楚；如有返回或反馈，使用较轻线条。",
        }
    return {
        "chart_type": "process_flow",
        "template_id": template_id,
        "title": title,
        "subtitle": "两行蛇形流程，避免长流程横向裁切",
        "language": "zh-CN",
        "style_profile": STYLE_PROFILE,
        "steps": [{"title": s["title"], "icon": s["icon"], "items": s["bullets"]} for s in stages],
    }


def _extract_modules(text: str) -> list[str]:
    body = _between(text, "包含") or _between(text, "包括") or _between(text, "由") or text
    items = _split_list(body)
    return [item for item in items if 1 <= len(item) <= 24]


def _compile_architecture(text: str) -> dict[str, Any]:
    modules = _extract_modules(text) or ["甲模块", "乙模块", "丙模块"]
    if len(modules) <= 4:
        layers = [
            {"label": f"第 {i + 1} 层", "title": item, "desc": f"承担{item}的稳定职责。"}
            for i, item in enumerate(modules)
        ]
        return {
            "chart_type": "system_architecture",
            "template_id": "vertical_layers",
            "title": _title_from_prompt(text, "系统架构图"),
            "language": "zh-CN",
            "style_profile": STYLE_PROFILE,
            "layers": layers,
        }
    return {
        "chart_type": "system_architecture",
        "template_id": "service_topology",
        "title": _title_from_prompt(text, "系统架构图"),
        "subtitle": "模块协作关系",
        "language": "zh-CN",
        "style_profile": STYLE_PROFILE,
        "gateway": {"title": modules[0], "desc": "统一入口或核心协调模块"},
        "services": [{"title": item, "desc": f"承担{item}职责"} for item in modules[1:6]],
        "queue": {"title": "共享组件", "desc": "用于解耦或共享访问"},
        "note": "实线表示主调用，虚线表示辅助或异步关系。",
    }


def _compile_comparison(text: str) -> dict[str, Any]:
    columns = _comparison_columns(text)
    dims = _split_list(_between(text, "维度包括") or _between(text, "对比维度包括") or _between(text, "维度"))
    if len(dims) < 2:
        dims = ["资源消耗", "处理速度", "效果表现", "适用场景"]
    if len(columns) > 2:
        return {
            "chart_type": "comparison",
            "template_id": "comparison_matrix_multi",
            "title": _title_from_prompt(text, "多对象对比"),
            "subtitle": " / ".join(columns),
            "language": "zh-CN",
            "style_profile": STYLE_PROFILE,
            "columns": columns[:4],
            "dimensions": [
                {"title": dim, "desc": _dimension_desc(dim), "scores": {col: 3 for col in columns[:4]}, "bullets": {col: [f"{col}在该维度待评估"] for col in columns[:4]}}
                for dim in dims[:5]
            ],
        }
    return {
        "chart_type": "comparison",
        "template_id": "comparison_matrix",
        "title": _title_from_prompt(text, f"{columns[0]}与{columns[1]}对比"),
        "language": "zh-CN",
        "style_profile": STYLE_PROFILE,
        "columns": columns[:2],
        "dimensions": [
            {
                "title": dim,
                "desc": _dimension_desc(dim),
                "left": {"tag": "观察", "score": 3, "bullets": _comparison_bullets(columns[0], dim)},
                "right": {"tag": "观察", "score": 3, "bullets": _comparison_bullets(columns[1], dim)},
            }
            for dim in dims[:4]
        ],
    }


def _comparison_columns(text: str) -> list[str]:
    vs_match = re.search(r"(.+?)\s+(?:vs|VS|对比|比较)\s+(.+?)(?:[，,。.]|$)", text)
    if vs_match:
        return [vs_match.group(1).strip()[-16:] or "甲", vs_match.group(2).strip()[:16] or "乙"]
    items = _split_list(_between(text, "比较") or _between(text, "对比") or "")
    if len(items) >= 2:
        return items[:4]
    return ["甲方案", "乙方案"]


def _dimension_desc(dim: str) -> str:
    if "资源" in dim:
        return "完成目标所需资源"
    if "速度" in dim:
        return "完成处理所需时间"
    if "效果" in dim:
        return "最终表现与能力上限"
    if "场景" in dim:
        return "更适合的使用环境"
    return "关键评价维度"


def _comparison_bullets(subject: str, dim: str) -> list[str]:
    return [f"{subject}在{dim}上的表现", "需结合实际约束判断"]


def _compile_decision(text: str) -> dict[str, Any]:
    root_match = re.search(r"([^，。；;？?]+是否[^，。；;？?]+[？?]?)", text)
    root = root_match.group(1).strip("？?") + "？" if root_match else "你的主要条件是否成立？"
    matches = re.findall(r"([^，。；;：:]+?)→选择\s*([^，。；;]+)", text)
    if matches:
        branches = [{"label": str(i + 1), "condition": c.strip(), "title": v.strip(), "bullets": _bullets_for(v.strip(), 2)} for i, (c, v) in enumerate(matches[:4])]
        template = "decision_cards"
    else:
        branches = [
            {"label": "是", "condition": "条件成立", "title": "甲路径", "bullets": ["采用甲路径", "继续检查后续条件"]},
            {"label": "否", "condition": "条件不成立", "title": "乙路径", "bullets": ["采用乙路径", "降低复杂度"]},
        ]
        template = "decision_branch_tree"
    return {
        "chart_type": "decision_tree",
        "template_id": template,
        "title": _title_from_prompt(text, "决策树"),
        "subtitle": "根据条件分支选择方案",
        "language": "zh-CN",
        "style_profile": STYLE_PROFILE,
        "root": {"title": root},
        "branches": branches,
    }


def _compile_timeline(text: str) -> dict[str, Any]:
    pairs = [{"year": y, "title": title.strip()} for y, title in re.findall(r"((?:19|20)\d{2})年?([^，。；;\n]+)", text)]
    if len(pairs) < 3:
        pairs = [{"year": str(2020 + i), "title": f"{_GENERIC_WORDS[i]}阶段"} for i in range(4)]
    return {
        "chart_type": "timeline",
        "template_id": "horizontal_timeline",
        "title": _title_from_prompt(text, "时间线"),
        "language": "zh-CN",
        "style_profile": STYLE_PROFILE,
        "events": [{"year": p["year"], "title": p["title"], "bullets": _timeline_bullets(p["title"])} for p in pairs[:7]],
    }


def _timeline_bullets(title: str) -> list[str]:
    return [f"{title}发生关键变化", "能力或状态持续演进", "影响后续阶段"]


def _compile_taxonomy(text: str) -> dict[str, Any]:
    root_match = re.search(r"根节点为[“\"']?([^”\"'，,。]+)", text)
    root = root_match.group(1).strip() if root_match else _title_from_prompt(text, "分类图")
    first_level = _split_list(_between(text, "分为") or _between(text, "一级分为"))
    groups = [{"title": item, "items": _children_after(text, item)} for item in first_level[:4]] if first_level else []
    if not groups:
        groups = [{"title": "甲类", "items": ["甲一"]}, {"title": "乙类", "items": ["乙一"]}]
    return {
        "chart_type": "taxonomy",
        "template_id": "taxonomy_tree",
        "title": _title_from_prompt(text, root),
        "language": "zh-CN",
        "style_profile": STYLE_PROFILE,
        "root": root,
        "groups": groups,
    }


def _children_after(text: str, group: str) -> list[str]:
    match = re.search(re.escape(group) + r"(?:下有|包括|包含)([^，。；;]+)", text)
    return _split_list(match.group(1))[:6] if match else []


def _compile_concept(text: str) -> dict[str, Any]:
    items = _split_list(_between(text, "包含") or _between(text, "包括") or _between(text, "关系"))
    if len(items) < 3:
        items = ["甲概念", "乙概念", "丙概念", "丁概念"]
    return {
        "chart_type": "concept",
        "template_id": "hub_spoke_concept",
        "title": _title_from_prompt(text, "概念关系图"),
        "language": "zh-CN",
        "style_profile": STYLE_PROFILE,
        "center": {"title": _title_from_prompt(text, "核心概念"), "desc": "核心组织对象"},
        "items": [{"title": item, "desc": "与中心概念相关"} for item in items[:8]],
    }


def _compile_mechanism(text: str) -> dict[str, Any]:
    terms = _split_list(_between(text, "包含") or _between(text, "包括") or text)[:6]
    if len(terms) < 3:
        terms = ["输入", "中间对象", "控制关系", "输出"]
    return {
        "chart_type": "mechanism",
        "template_id": "mechanism_mapping",
        "title": _title_from_prompt(text, "机制原理图"),
        "language": "zh-CN",
        "style_profile": STYLE_PROFILE,
        "sections": [{"title": term, "desc": "说明该对象在机制中的作用"} for term in terms[:6]],
        "formula": "按用户原文保留公式或变量关系" if _contains_any(text, ["=", "矩阵", "向量", "公式"]) else "",
    }


def _compile_infographic(text: str) -> dict[str, Any]:
    items = _split_list(_between(text, "包含") or _between(text, "要点") or _between(text, "包括"))
    if len(items) < 3:
        items = ["甲模块", "乙模块", "丙模块", "丁模块"]
    return {
        "chart_type": "infographic",
        "template_id": "grouped_infographic",
        "title": _title_from_prompt(text, "信息图"),
        "subtitle": "围绕主题组织多个认知模块",
        "language": "zh-CN",
        "style_profile": STYLE_PROFILE,
        "cards": [
            {
                "title": item,
                "summary": _bullets_for(item, 1)[0],
                "items": _bullets_for(item, 3)[1:] or ["关键要点", "应用说明"],
                "tags": [f"要点 {i + 1}"],
            }
            for i, item in enumerate(items[:8])
        ],
    }
