"""DiagramSpec 校验与归一化。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.figures.render.html_template.schema import (
    STYLE_PROFILE,
    TEMPLATE_LIMITS,
    default_template_for_subtype,
)

_LEGACY_TEMPLATE_ALIASES = {
    "rag" + "_three_column": "shared_resource_three_column",
    "attention" + "_mechanism": "mechanism_sequence",
    "encoder_decoder" + "_architecture": "parallel_stack_architecture",
}


def _normalize_template_id(spec: dict[str, Any], repairs: list[str]) -> None:
    template_id = str(spec.get("template_id") or "")
    replacement = _LEGACY_TEMPLATE_ALIASES.get(template_id)
    if replacement:
        spec["template_id"] = replacement
        repairs.append("旧模板 id 已映射到通用模板。")


def _truncate(text: Any, max_chars: int) -> str:
    s = str(text or "").strip()
    return s if len(s) <= max_chars else s[: max_chars - 1].rstrip() + "…"


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    return [value]


def _title_of(obj: Any) -> str:
    if isinstance(obj, dict):
        return str(obj.get("title") or obj.get("name") or obj.get("label") or obj.get("text") or "").strip()
    return str(obj or "").strip()


def _desc_of(obj: Any) -> str:
    if isinstance(obj, dict):
        return str(obj.get("desc") or obj.get("description") or obj.get("summary") or obj.get("body") or "").strip()
    return ""


def _items_of(obj: Any) -> list[Any]:
    if not isinstance(obj, dict):
        return []
    return _as_list(obj.get("items") or obj.get("bullets") or obj.get("children") or obj.get("points") or obj.get("subitems"))


def _walk(obj: Any, fn, path: str = "", parent: Any = None, key: Any = None) -> None:
    fn(obj, path, parent, key)
    if isinstance(obj, list):
        for i, value in enumerate(obj):
            _walk(value, fn, f"{path}[{i}]", obj, i)
    elif isinstance(obj, dict):
        for child_key, value in list(obj.items()):
            _walk(value, fn, f"{path}.{child_key}" if path else str(child_key), obj, child_key)


def _ensure_ids(spec: dict[str, Any], repairs: list[str]) -> None:
    for field in ("stages", "steps", "cards", "layers", "branches", "events", "dimensions", "groups", "items", "sections", "services"):
        arr = spec.get(field)
        if not isinstance(arr, list):
            continue
        for i, item in enumerate(arr):
            if isinstance(item, dict) and not item.get("id"):
                item["id"] = f"{field}-{i}"
    repairs.append("补全组件 id。")


def _normalize_text_density(spec: dict[str, Any], repairs: list[str]) -> None:
    if spec.get("title"):
        old = str(spec["title"])
        spec["title"] = _truncate(old, 32)
        if spec["title"] != old:
            repairs.append("压缩过长 title。")
    if spec.get("subtitle"):
        spec["subtitle"] = _truncate(spec["subtitle"], 56)
    if spec.get("note"):
        spec["note"] = _truncate(spec["note"], 96)

    def trim_strings(value: Any, path: str, parent: Any, key: Any) -> None:
        if not isinstance(value, str) or parent is None:
            return
        limit = 30 if str(path).endswith((".title", ".label", ".condition", ".year")) else 52
        trimmed = _truncate(value, limit)
        if trimmed != value:
            parent[key] = trimmed
            repairs.append(f"压缩长文本 {path}。")

    _walk(spec, trim_strings)

    def limit_lists(value: Any, path: str, parent: Any, key: Any) -> None:
        if not isinstance(value, list) or key not in {"bullets", "items", "io"}:
            return
        if len(value) > 3:
            parent[key] = value[:3]
            repairs.append(f"限制 {path} 为最多 3 条。")

    _walk(spec, limit_lists)


def _normalize_aliases(spec: dict[str, Any], repairs: list[str]) -> None:
    """Repair common LLM output aliases to renderer schema."""
    template = str(spec.get("template_id") or "")

    # Generic title aliases.
    if not spec.get("title"):
        for key in ("name", "label", "heading"):
            if spec.get(key):
                spec["title"] = spec[key]
                repairs.append(f"{key} → title。")
                break

    if template == "horizontal_stage_cards":
        arr = spec.get("stages") or spec.get("steps") or spec.get("nodes") or spec.get("modules")
        spec["stages"] = [_normalize_stage(x, i, len(_as_list(arr))) for i, x in enumerate(_as_list(arr))]

    elif template == "snake_cards":
        arr = spec.get("steps") or spec.get("stages") or spec.get("nodes") or spec.get("modules")
        spec["steps"] = [_normalize_step(x) for x in _as_list(arr)]

    elif template == "grouped_infographic":
        arr = spec.get("cards") or spec.get("modules") or spec.get("nodes") or spec.get("items")
        spec["cards"] = [_normalize_card(x, i) for i, x in enumerate(_as_list(arr))]

    elif template == "vertical_layers":
        arr = spec.get("layers") or spec.get("modules") or spec.get("nodes")
        spec["layers"] = [_normalize_layer(x, i) for i, x in enumerate(_as_list(arr))]

    elif template == "shared_resource_three_column":
        _normalize_three_column(spec)

    elif template in {"comparison_matrix", "comparison_matrix_multi"}:
        spec["columns"] = _as_list(spec.get("columns") or spec.get("subjects") or spec.get("objects")) or spec.get("columns") or []
        dims = spec.get("dimensions") or spec.get("rows") or spec.get("criteria") or spec.get("metrics")
        spec["dimensions"] = [_normalize_dimension(x, spec.get("columns") or []) for x in _as_list(dims)]

    elif template in {"decision_cards", "decision_branch_tree"}:
        if not spec.get("root"):
            spec["root"] = {"title": spec.get("question") or "你的主要需求是什么？"}
        arr = spec.get("branches") or spec.get("options") or spec.get("results") or spec.get("children")
        spec["branches"] = [_normalize_branch(x, i) for i, x in enumerate(_as_list(arr))]

    elif template == "taxonomy_tree":
        root = spec.get("root") or spec.get("center") or spec.get("title") or "分类"
        if isinstance(root, dict):
            root = _title_of(root) or "分类"
        spec["root"] = root
        arr = spec.get("groups") or spec.get("categories") or spec.get("children") or spec.get("items")
        spec["groups"] = [_normalize_group(x) for x in _as_list(arr)]

    elif template in {"mechanism_mapping", "mechanism_sequence"}:
        arr = spec.get("sections") or spec.get("steps") or spec.get("nodes") or spec.get("modules")
        spec["sections"] = [_normalize_section(x) for x in _as_list(arr)]

    elif template == "parallel_stack_architecture":
        spec["encoder_layers"] = _as_list(spec.get("encoder_layers") or spec.get("encoder") or ["甲层", "乙层", "丙层"])
        spec["decoder_layers"] = _as_list(spec.get("decoder_layers") or spec.get("decoder") or ["丁层", "戊层", "己层"])

    elif template == "service_topology":
        spec["services"] = [_normalize_service(x) for x in _as_list(spec.get("services") or spec.get("modules") or spec.get("nodes"))]

    repairs.append("归一化常见字段别名。")


def _normalize_stage(x: Any, i: int, total: int) -> dict[str, Any]:
    title = _title_of(x) or f"阶段 {i + 1}"
    items = _items_of(x)
    return {
        "title": title,
        "icon": (x.get("icon") if isinstance(x, dict) else "") or "card",
        "bullets": items or [_desc_of(x) or "完成本阶段核心任务"],
        "io": _as_list(x.get("io") if isinstance(x, dict) else [])[:2],
        "connector": (x.get("connector") if isinstance(x, dict) else "") or ("进入\n下一步" if i < total - 1 else ""),
    }


def _normalize_step(x: Any) -> dict[str, Any]:
    title = _title_of(x) or "步骤"
    return {"title": title, "icon": (x.get("icon") if isinstance(x, dict) else "") or "card", "items": _items_of(x) or [_desc_of(x) or "完成核心处理"]}


def _normalize_card(x: Any, i: int) -> dict[str, Any]:
    title = _title_of(x) or f"模块 {i + 1}"
    items = _items_of(x)
    return {"title": title, "summary": _desc_of(x) or (str(items[0]) if items else "核心说明"), "items": items[1:3] if len(items) > 1 else items, "tags": _as_list(x.get("tags") if isinstance(x, dict) else [])}


def _normalize_layer(x: Any, i: int) -> dict[str, Any]:
    return {"label": (x.get("label") if isinstance(x, dict) else "") or f"第 {i + 1} 层", "title": _title_of(x) or f"第 {i + 1} 层模块", "desc": _desc_of(x) or "说明该层职责和数据流。", "icon": (x.get("icon") if isinstance(x, dict) else "") or "card"}


def _normalize_three_column(spec: dict[str, Any]) -> None:
    for side in ("left", "right"):
        block = spec.get(side) if isinstance(spec.get(side), dict) else {}
        mods = block.get("modules") or block.get("items") or block.get("children") or []
        block["modules"] = [{"title": _title_of(m) or "模块", "desc": _desc_of(m) or "核心处理步骤"} for m in _as_list(mods)]
        spec[side] = block
    if not isinstance(spec.get("center"), dict):
        spec["center"] = {"title": "共享组件", "desc": "供两侧模块共同访问"}


def _normalize_dimension(x: Any, columns: list[Any]) -> dict[str, Any]:
    if not isinstance(x, dict):
        return {"title": str(x), "desc": "关键评价维度", "left": {"tag": "", "score": 3, "bullets": []}, "right": {"tag": "", "score": 3, "bullets": []}}
    d = {"title": _title_of(x) or "维度", "desc": _desc_of(x) or "关键评价维度"}
    if "scores" in x or len(columns) > 2:
        d["scores"] = x.get("scores") or {}
        d["bullets"] = x.get("bullets") or {}
    else:
        d["left"] = x.get("left") or x.get("a") or {"tag": "", "score": 3, "bullets": []}
        d["right"] = x.get("right") or x.get("b") or {"tag": "", "score": 3, "bullets": []}
    return d


def _normalize_branch(x: Any, i: int) -> dict[str, Any]:
    if isinstance(x, dict):
        return {"label": x.get("label") or x.get("condition") or ("是" if i == 0 else "否"), "condition": x.get("condition") or x.get("label") or "", "title": _title_of(x) or f"结果 {i + 1}", "bullets": _items_of(x) or _as_list(x.get("bullets")) or [x.get("desc") or "给出对应建议"]}
    return {"label": "", "condition": "", "title": str(x), "bullets": ["给出对应建议"]}


def _normalize_group(x: Any) -> dict[str, Any]:
    if isinstance(x, dict):
        return {"title": _title_of(x) or "类别", "items": [str(v) if not isinstance(v, dict) else _title_of(v) for v in _items_of(x)]}
    return {"title": str(x), "items": []}


def _normalize_section(x: Any) -> dict[str, Any]:
    return {"title": _title_of(x) or "机制步骤", "desc": _desc_of(x) or "说明该步骤的作用。"}


def _normalize_service(x: Any) -> dict[str, Any]:
    return {"title": _title_of(x) or "服务模块", "desc": _desc_of(x) or "处理独立业务能力。"}


def _apply_topic_presets(spec: dict[str, Any], repairs: list[str]) -> None:
    """当 LLM 只给骨架时，使用通用占位补齐空槽。"""
    template = str(spec.get("template_id") or "")

    if template == "vertical_layers" and _empty_list(spec.get("layers")):
        spec["layers"] = [
            {"label": "第一层", "title": "甲模块", "desc": "接收输入并完成初步处理。"},
            {"label": "第二层", "title": "乙模块", "desc": "执行核心逻辑并协调下游。"},
            {"label": "第三层", "title": "丙模块", "desc": "保存结果或提供共享能力。"},
        ]
        repairs.append("按通用分层结构补全 layers。")

    if template == "shared_resource_three_column":
        if not spec.get("left") or _empty_list((spec.get("left") or {}).get("modules")):
            spec["left"] = {"title": "左侧处理区", "subtitle": "输入侧", "modules": [{"title": "甲", "desc": "完成甲处理"}, {"title": "乙", "desc": "完成乙处理"}]}
        if not spec.get("right") or _empty_list((spec.get("right") or {}).get("modules")):
            spec["right"] = {"title": "右侧处理区", "subtitle": "输出侧", "modules": [{"title": "丙", "desc": "完成丙处理"}, {"title": "丁", "desc": "完成丁处理"}]}
        spec.setdefault("center", {"title": "共享组件", "desc": "供两侧模块共同访问"})
        repairs.append("按通用三栏结构补全模块。")

    if template == "taxonomy_tree" and _empty_list(spec.get("groups")):
        spec["root"] = spec.get("root") or spec.get("title") or "分类"
        spec["groups"] = [{"title": "甲类", "items": ["甲一", "甲二"]}, {"title": "乙类", "items": ["乙一", "乙二"]}]
        repairs.append("按通用分类结构补全 groups。")

    if template == "comparison_matrix" and len(spec.get("columns") or []) > 2:
        spec["template_id"] = "comparison_matrix_multi"
        spec["dimensions"] = [
            {"title": "甲维度", "desc": "第一项评价维度", "scores": {col: 3 for col in spec.get("columns") or []}},
            {"title": "乙维度", "desc": "第二项评价维度", "scores": {col: 3 for col in spec.get("columns") or []}},
        ]
        repairs.append("多对象对比切换为多对象矩阵。")


def _empty_list(value: Any) -> bool:
    return not isinstance(value, list) or len(value) == 0


def _fallback_horizontal(spec: dict[str, Any], repairs: list[str]) -> None:
    stages = spec.get("stages")
    if not isinstance(stages, list) or len(stages) <= TEMPLATE_LIMITS["horizontal_stage_cards"].max:
        return
    if len(stages) <= TEMPLATE_LIMITS["snake_cards"].max:
        spec["template_id"] = "snake_cards"
        spec["chart_type"] = "process_flow"
        spec["steps"] = [{"id": item.get("id"), "title": item.get("title", ""), "icon": item.get("icon", "step"), "items": item.get("bullets") or item.get("items") or []} for item in stages]
        spec.pop("stages", None)
        repairs.append("horizontal_stage_cards 超容量，切换为 snake_cards。")
    else:
        spec["template_id"] = "grouped_infographic"
        spec["chart_type"] = "infographic"
        spec["cards"] = [{"id": item.get("id"), "title": item.get("title", ""), "summary": (item.get("bullets") or item.get("items") or [""])[0], "items": (item.get("bullets") or item.get("items") or [])[1:4], "tags": [f"模块 {i + 1}"]} for i, item in enumerate(stages[:8])]
        spec.pop("stages", None)
        repairs.append("horizontal_stage_cards 严重超容量，切换为 grouped_infographic。")


def _fallback_snake(spec: dict[str, Any], repairs: list[str]) -> None:
    steps = spec.get("steps")
    if not isinstance(steps, list) or len(steps) <= TEMPLATE_LIMITS["snake_cards"].max:
        return
    spec["template_id"] = "grouped_infographic"
    spec["chart_type"] = "infographic"
    spec["cards"] = [{"id": item.get("id"), "title": item.get("title", ""), "summary": (item.get("items") or [""])[0], "items": (item.get("items") or [])[1:4], "tags": [f"模块 {i + 1}"]} for i, item in enumerate(steps[:8])]
    spec.pop("steps", None)
    repairs.append("snake_cards 超容量，切换为 grouped_infographic。")


def _limit_template_arrays(spec: dict[str, Any], messages: list[str], repairs: list[str]) -> None:
    template_id = str(spec.get("template_id") or "")
    limit = TEMPLATE_LIMITS.get(template_id)
    if not limit or not limit.field:
        return
    arr = spec.get(limit.field)
    if arr is None:
        spec[limit.field] = []
        arr = spec[limit.field]
    if not isinstance(arr, list):
        messages.append(f"{limit.field} 必须是数组。")
        spec[limit.field] = []
        return
    if limit.max and len(arr) > limit.max:
        spec[limit.field] = arr[: limit.max]
        repairs.append(f"裁剪 {limit.field} 到模板容量 {limit.max}。")
    if limit.min and len(spec[limit.field]) < limit.min:
        messages.append(f"{template_id}: {limit.field} 数量偏少，建议补充信息。")


def _required_slot_errors(spec: dict[str, Any]) -> list[str]:
    template = str(spec.get("template_id") or "")
    errors: list[str] = []

    def require(cond: bool, msg: str) -> None:
        if not cond:
            errors.append(msg)

    if template == "horizontal_stage_cards":
        for i, s in enumerate(spec.get("stages") or []):
            require(bool(s.get("title")), f"stage[{i}].title 为空")
            require(bool(s.get("bullets") or s.get("items")), f"stage[{i}].bullets 为空")
    elif template == "snake_cards":
        for i, s in enumerate(spec.get("steps") or []):
            require(bool(s.get("title")), f"step[{i}].title 为空")
            require(bool(s.get("items") or s.get("bullets")), f"step[{i}].items 为空")
    elif template == "vertical_layers":
        for i, l in enumerate(spec.get("layers") or []):
            require(bool(l.get("title")), f"layer[{i}].title 为空")
            require(bool(l.get("desc")), f"layer[{i}].desc 为空")
    elif template == "shared_resource_three_column":
        require(bool((spec.get("left") or {}).get("modules")), "left.modules 为空")
        require(bool((spec.get("right") or {}).get("modules")), "right.modules 为空")
        require(bool((spec.get("center") or {}).get("title")), "center.title 为空")
    elif template == "taxonomy_tree":
        for i, g in enumerate(spec.get("groups") or []):
            require(bool(g.get("title")), f"group[{i}].title 为空")
            require(bool(g.get("items")), f"group[{i}].items 为空")
    elif template in {"comparison_matrix", "comparison_matrix_multi"}:
        require(len(spec.get("columns") or []) >= 2, "comparison columns 不足")
        for i, d in enumerate(spec.get("dimensions") or []):
            require(bool(d.get("title")), f"dimension[{i}].title 为空")
    elif template in {"decision_cards", "decision_branch_tree"}:
        require(bool((spec.get("root") or {}).get("title")), "decision root.title 为空")
        for i, b in enumerate(spec.get("branches") or []):
            require(bool(b.get("title")), f"branch[{i}].title 为空")
            require(bool(b.get("bullets")), f"branch[{i}].bullets 为空")
    elif template in {"mechanism_mapping", "mechanism_sequence"}:
        for i, sec in enumerate(spec.get("sections") or []):
            require(bool(sec.get("title")), f"section[{i}].title 为空")
            require(bool(sec.get("desc")), f"section[{i}].desc 为空")
    elif template == "parallel_stack_architecture":
        require(bool(spec.get("encoder_layers")), "encoder_layers 为空")
        require(bool(spec.get("decoder_layers")), "decoder_layers 为空")
    elif template == "service_topology":
        require(bool(spec.get("gateway") or spec.get("services")), "service_topology 缺少 gateway/services")
        require(len(spec.get("services") or []) >= 2, "services 数量不足")
    return errors


def validate_and_normalize(input_spec: dict[str, Any], *, subtype: str = "") -> dict[str, Any]:
    messages: list[str] = []
    repairs: list[str] = []

    if not isinstance(input_spec, dict):
        return {"ok": False, "severity": "err", "messages": ["DiagramSpec 不是对象。"], "spec": input_spec}
    if input_spec.get("needs_clarification"):
        return {"ok": False, "severity": "warn", "messages": ["需要追问：", *(input_spec.get("questions") or []), input_spec.get("reason") or ""], "spec": input_spec}

    spec = deepcopy(input_spec)
    spec["language"] = spec.get("language") or "zh-CN"
    spec["style_profile"] = spec.get("style_profile") or STYLE_PROFILE
    spec["title"] = spec.get("title") or spec.get("name") or "未命名图示"
    _normalize_template_id(spec, repairs)
    if not spec.get("template_id") or spec.get("template_id") not in TEMPLATE_LIMITS:
        spec["template_id"] = default_template_for_subtype(subtype)
        repairs.append("按 subtype 补全 template_id。")
    if not spec.get("chart_type"):
        spec["chart_type"] = TEMPLATE_LIMITS[spec["template_id"]].chart_type

    _normalize_aliases(spec, repairs)
    _apply_topic_presets(spec, repairs)
    _normalize_text_density(spec, repairs)
    _fallback_horizontal(spec, repairs)
    _fallback_snake(spec, repairs)
    _normalize_aliases(spec, repairs)
    _limit_template_arrays(spec, messages, repairs)
    _ensure_ids(spec, repairs)

    slot_errors = _required_slot_errors(spec)
    if slot_errors:
        messages.extend(slot_errors)
        return {"ok": False, "severity": "err", "messages": messages + [f"修复：{x}" for x in repairs], "spec": spec}

    severity = "warn" if messages else "ok"
    return {"ok": True, "severity": severity, "messages": (messages or ["通过：模板合法，可渲染。"]) + [f"修复：{x}" for x in repairs], "spec": spec}
