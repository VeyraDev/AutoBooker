"""System architecture parser."""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析系统架构 JSON。只输出 JSON：
{
  "title": "短标题，不超过12个中文字符",
  "layers": [
    {"label":"入口层", "modules":["API网关"]},
    {"label":"服务层", "modules":["用户服务","订单服务","支付服务"]},
    {"label":"基础设施层", "modules":["消息队列","数据库"]}
  ],
  "connections": [
    {"from":"API网关", "to":"用户服务", "label":""},
    {"from":"订单服务", "to":"消息队列", "label":"异步"}
  ]
}
规则：
1. layers 表示层级/区域；modules 是该层的真实模块短名；connections 表示跨层调用或数据流。
2. 根据语义识别真实模块。描述中出现"X连接前N个服务""X通过Y通知Z""X包含N个模块"等聚合关系句，把它们转成 connections，不要把整句写进 modules。
3. modules 每条最多10个中文字符；禁止写"完整架构图""左侧模块""用箭头连接""连接前三个服务""通过消息队列异步通知支付服务"等版式说明或关系句。
4. connections.label 只写极短的关系词（"HTTP""SQL""异步""事件"），或留空；禁止写整句话。
5. 若某条描述整体是"说明如何排版布局"（如"左边放入口层，右边放服务层"），直接忽略，不影响 layers/modules 提取。
6. title 只给语义图题，禁止包含"共X个""前N个""通过"等关系描述词。
描述：{text}
"""

_LAYER_PATTERNS = [
    ("前端层", r"(?:顶层|前端|客户端)[是为：:]*([^，,。；;]+)"),
    ("服务层", r"(?:中间层|后端|服务层)[是为：:]*([^，,。；;]+)"),
    ("数据层", r"(?:底层|数据库|数据层)[是为：:]*([^，,。；;]+)"),
]


def _short(text: Any, limit: int = 22) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。")
    raw = re.sub(r"^(?:微服务架构图|系统架构图|架构图)$", "", raw)
    raw = re.sub(r"(?:\d+|[一二两三四五六七八九十])\s*个(?:模块|服务|组件)$", "", raw)
    return raw[:limit].strip(" ：:，,。")

# 关系/计数/版式短语 → 说明文字，不是模块名
_ANNOTATION_RE = re.compile(
    r"连接前|连接后|连接所有|通过消息|异步通知|同步通知|"
    r"共[一二两三四五六七八九十\d]+个|"
    r"前[一二两三四五六七八九十\d]+个|"
    r"后[一二两三四五六七八九十\d]+个|"
    r"包含[一二两三四五六七八九十\d]+|"
    r"有[一二两三四五六七八九十\d]+个|"
    r"五个模块|四个服务|三个服务|两个服务"
)

def _is_annotation(text: str) -> bool:
    """True if the string is a relational/layout description, not a module name."""
    return bool(_ANNOTATION_RE.search(str(text or "")))

def _split_modules(text: str) -> list[str]:
    parts = re.split(r"[、,，/]|和|与", str(text or ""))
    modules: list[str] = []
    for part in parts:
        module = _clean_module_name(part)
        if module and module not in modules:
            modules.append(module)
    return modules


def _clean_module_name(text: Any) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。")
    raw = re.sub(r"^(?:包含|包括|有|模块|组件)[:：]?\s*", "", raw)
    raw = re.sub(r"^(?:微服务架构图|系统架构图|架构图)$", "", raw)
    raw = re.sub(r"(?:\d+|[一二两三四五六七八九十])\s*个(?:模块|服务|组件)$", "", raw)
    raw = re.split(r"(?:连接|通过|异步|同步|通知|调用|返回|依赖)", raw, 1)[0]
    # 剪断所有关系动词及其后内容
    for verb in ("连接", "通过", "异步", "同步", "通知", "调用", "依赖", "返回", "触发"):
        if verb in raw:
            raw = raw.split(verb, 1)[0].strip(" ：:，,。")
    # 硬限 10 个中文字符（约 140px，足够渲染）
    return _short(raw.strip(" ：:，,。"), 10)


def _declared_modules(text: str) -> list[str]:
    patterns = [
        r"(?:包含|包括|有)[:：]?\s*(.+?)(?:\d+|[一二两三四五六七八九十])\s*个(?:模块|服务|组件)",
        r"(?:包含|包括|有)[:：]?\s*([^。；;]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        modules = _split_modules(m.group(1))
        if modules:
            return modules
    return _split_modules(text)


def _module_layers(modules: list[str]) -> list[dict[str, Any]]:
    gateways = [m for m in modules if "网关" in m or "入口" in m]
    infra = [m for m in modules if re.search(r"队列|数据库|缓存|存储|消息", m)]
    services = [m for m in modules if m not in gateways and m not in infra]
    layers: list[dict[str, Any]] = []
    if gateways:
        layers.append({"label": "入口层", "modules": gateways})
    if services:
        layers.append({"label": "服务层", "modules": services})
    if infra:
        layers.append({"label": "基础设施层", "modules": infra})
    return layers or [{"label": "模块层", "modules": modules[:6] or ["应用模块"]}]


def _rule_connections(text: str, layers: list[dict[str, Any]]) -> list[dict[str, str]]:
    modules = [m for layer in layers for m in layer.get("modules", [])]
    services = [m for m in modules if "服务" in m]
    gateways = [m for m in modules if "网关" in m or "入口" in m]
    connections: list[dict[str, str]] = []

    # 通用聚合关系句：X 连接前/所有/N 个 服务/模块/组件
    _AGGREGATE_RE = re.compile(
        r"([^，,。；;\s]{1,10}?)[连接]{2}"
        r"(?:前|所有|全部)?(?:[一二两三四五六七八九十]|\d)+个(?:服务|模块|组件)"
    )
    for m in _AGGREGATE_RE.finditer(text):
        src = _match_module(m.group(1), modules)
        if src:
            targets = [t for t in services if t != src][:3]
            for target in targets:
                connections.append({"from": src, "to": target, "label": ""})

    for m in re.finditer(r"([^，,。；;\s]+?)通过([^，,。；;\s]+?)(?:异步|同步)?通知([^，,。；;\s]+)", text):
        src = _match_module(m.group(1), modules)
        via = _match_module(m.group(2), modules)
        dst = _match_module(m.group(3), modules)
        label = "异步" if "异步" in m.group(0) else "通知"
        if src and via:
            connections.append({"from": src, "to": via, "label": label})
        if via and dst:
            connections.append({"from": via, "to": dst, "label": label})

    for m in re.finditer(r"([^，,。；;\s]+?)连接([^，,。；;]+)", text):
        src = _match_module(m.group(1), modules)
        if not src:
            continue
        targets = [_match_module(part, modules) for part in _split_modules(m.group(2))]
        for target in targets:
            if target and src != target:
                connections.append({"from": src, "to": target, "label": ""})

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for conn in connections:
        key = (conn["from"], conn["to"], conn.get("label", ""))
        if key not in seen:
            deduped.append(conn)
            seen.add(key)
    return deduped


def _match_module(fragment: str, modules: list[str]) -> str:
    cleaned = _clean_module_name(fragment)
    if not cleaned:
        return ""
    for module in modules:
        if cleaned == module or cleaned in module or module in cleaned:
            return module
    return cleaned if cleaned in modules else ""


def _normalize_layers(raw: Any) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return layers
    for item in raw[:6]:
        if not isinstance(item, dict):
            continue
        label = _short(item.get("label") or item.get("name") or item.get("layer"), 16)
        modules_raw = item.get("modules") or item.get("components") or []
        modules = [
            m for m in (
                [_clean_module_name(m) for m in modules_raw if _clean_module_name(m)]
                if isinstance(modules_raw, list)
                else _split_modules(str(modules_raw))
            )
            if m and not _is_annotation(m)
        ]
        modules = list(dict.fromkeys(modules))
        if label and modules:
            layers.append({"label": label, "modules": modules[:6]})
    return layers


def _rule_layers(text: str) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    for label, pattern in _LAYER_PATTERNS:
        m = re.search(pattern, text)
        if m:
            modules = _split_modules(m.group(1))
            if modules:
                layers.append({"label": label, "modules": modules[:4]})
    if layers:
        return layers

    modules = _declared_modules(text)
    return _module_layers(modules)


def _normalize_connections(raw: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw[:12]:
        if not isinstance(item, dict):
            continue
        src = _short(item.get("from") or item.get("source"), 20)
        dst = _short(item.get("to") or item.get("target"), 20)
        label = _short(item.get("label") or item.get("type"), 14)
        if src and dst:
            out.append({"from": src, "to": dst, "label": label})
    return out


def _to_graph(title: str, layers: list[dict[str, Any]], connections: list[dict[str, str]] | None = None) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    module_to_id: dict[str, str] = {}
    for li, layer in enumerate(layers):
        for mi, module in enumerate(layer["modules"]):
            nid = f"l{li}_m{mi}"
            nodes.append({"id": nid, "label": module, "shape": "box", "level": li, "column": mi})
            module_to_id[module] = nid
    if not connections:
        for left, right in zip(layers, layers[1:]):
            for src in left["modules"]:
                for dst in right["modules"][: max(1, min(2, len(right["modules"])))]:
                    edges.append({"from": module_to_id[src], "to": module_to_id[dst], "label": ""})
    seen_edges: set[tuple[str, str]] = set()
    for conn in connections or []:
        src = module_to_id.get(conn["from"])
        dst = module_to_id.get(conn["to"])
        if src and dst and (src, dst) not in seen_edges and (dst, src) not in seen_edges:
            edges.append({"from": src, "to": dst, "label": conn.get("label", "")})
            seen_edges.add((src, dst))
    return {
        "diagram_subtype": "system_architecture",
        "layout": "TB",
        "title": title or "系统架构",
        "structure_summary": f"{len(layers)} 层系统架构",
        "layers": layers,
        "connections": connections or [],
        "nodes": nodes,
        "edges": edges,
    }


def parse_architecture(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    model = (ctx.model or settings.intent_model).strip()
    if ctx.use_llm and model:
        try:
            out = LLMClient().chat_completion(
                [{"role": "user", "content": _PROMPT.format(text=ctx.normalized_input[:2500])}],
                model=model,
                max_tokens=2400,
                temperature=0.1,
            )
            data = parse_llm_json(out)
            if isinstance(data, dict):
                layers = _normalize_layers(data.get("layers"))
                if layers:
                    connections = _normalize_connections(data.get("connections"))
                    return ParsedDiagram(_to_graph(_short(data.get("title") or intent.title, 24), layers, connections), "llm_architecture")
        except Exception:
            pass
    layers = _rule_layers(ctx.normalized_input)
    connections = _rule_connections(ctx.normalized_input, layers)
    return ParsedDiagram(_to_graph(_short(intent.title or "系统架构", 24), layers, connections), "rules_architecture")
