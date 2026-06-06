"""Post-LLM diagram plan hygiene.

The parser should be semantic-first, but LLMs sometimes copy presentation
instructions into node labels. This module is a small reviewer that keeps those
labels diagram-ready without turning extraction back into comma-splitting.
"""

from __future__ import annotations

import html
import re
from typing import Any

from app.services.figures.schemas.diagram import ParsedDiagram

_ARROW_RE = re.compile(r"\s*(?:-&gt;|→|->|=>|⇒)\s*")
_TITLE_PREFIX_RE = re.compile(r"^图\s*\d+\s*[-–—]\s*\d+\s*[:：]\s*")
_BAD_LABEL_RE = re.compile(
    r"(完整|左侧|右侧|上方|下方|顶部|底部|中间|中心区域|图中|画面|展示|说明|绘制|生成|"
    r"用箭头|箭头连接|连线|布局|放置|排列|包含以下|包括以下)"
)
_SIDE_PREFIX_RE = re.compile(
    r"^(?:完整|整体|左侧|右侧|上方|下方|顶部|底部|中间|中心区域|图中|画面中|"
    r"展示|说明|绘制|生成|表示|呈现|放置|排列|包含|包括|模块)[:：\s]*"
)
_TRAILING_INSTRUCTION_RE = re.compile(
    r"(?:，|,|。|；|;)\s*(?:用|以|通过)?(?:箭头连接|箭头|连线|方框|色块|图标|布局|排列|展示|说明|连接).*$"
)


def visual_width(text: str) -> float:
    total = 0.0
    for ch in str(text or ""):
        if "\u4e00" <= ch <= "\u9fff":
            total += 1.0
        elif ch.isspace():
            total += 0.35
        else:
            total += 0.55
    return total


def clean_title(raw: Any, *, fallback: str = "示意图", max_units: float = 24) -> str:
    text = html.unescape(str(raw or "")).strip()
    text = _TITLE_PREFIX_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" ：:，,。")
    if not text:
        return fallback
    first = re.split(r"[，,。；;：:\n]", text, 1)[0].strip(" ：:，,。")
    candidate = first or text
    return _clip_visual(candidate, max_units=max_units, fallback=fallback)


def clean_label(raw: Any, *, fallback: str = "", max_units: float = 14) -> tuple[str, bool]:
    original = html.unescape(str(raw or "")).strip()
    text = re.sub(r"\s+", " ", original).strip(" ：:，,。")
    changed = False
    if not text:
        return fallback, bool(fallback)

    if _ARROW_RE.search(text) and _BAD_LABEL_RE.search(text):
        parts = [p.strip(" ：:，,。") for p in _ARROW_RE.split(text) if p.strip(" ：:，,。")]
        if parts:
            text = parts[-1]
            changed = True

    before = text
    text = re.sub(r"(?:\d+|[一二两三四五六七八九十])\s*个(?:模块|步骤|阶段|环节|分支|节点|服务|组件)$", "", text).strip(" ：:，,。")
    text = re.sub(r"(?:两个|两条|多个)?并行分支$", "", text).strip(" ：:，,。")
    text = _SIDE_PREFIX_RE.sub("", text).strip(" ：:，,。")
    text = re.sub(r"^(?:[（(]?(?:左|右|上|下|中|主)[）)]?\s*)", "", text).strip(" ：:，,。")
    text = re.sub(r"^(?:从|经过|最终|最后|然后|接着|再到|汇合后|汇合后进行|进行)", "", text).strip(" ：:，,。")
    text = _TRAILING_INSTRUCTION_RE.sub("", text).strip(" ：:，,。")
    if re.search(r"连接|通过|异步|同步|通知|调用|箭头连接", text):
        text = re.split(r"连接|通过|异步|同步|通知|调用|箭头连接", text, 1)[0].strip(" ：:，,。")
    text = re.sub(r"[，,]?用(?:箭头)?$", "", text).strip(" ：:，,。")
    text = re.sub(r"(?:开始|步骤)$", "", text).strip(" ：:，,。")
    text = re.sub(r"^(?:完整的?|整体的?)", "", text).strip(" ：:，,。")
    changed = changed or text != before

    text = _clip_visual(text, max_units=max_units, fallback=fallback or original[:12])
    return text, changed or text != original


def _clip_visual(text: str, *, max_units: float, fallback: str) -> str:
    raw = str(text or "").strip(" ：:，,。")
    if not raw:
        return fallback
    if visual_width(raw) <= max_units:
        return raw
    out = ""
    for ch in raw:
        if visual_width(out + ch) > max_units:
            break
        out += ch
    if out and out[-1].isalnum():
        out = re.sub(r"[A-Za-z0-9_]+$", "", out).rstrip() or raw[: int(max_units)]
    return out.strip(" ：:，,。") or fallback


def icon_hint(label: str, kind: str = "") -> str:
    text = str(label or "").lower()
    # 人/用户
    if re.search(r"user|用户|客户|读者|human|person|访客|管理员|admin", text):
        return "user"
    # 数据存储
    if re.search(r"data|数据库|向量库|知识库|store|db|sql|postgres|redis|es|elasticsearch|s3|存储|仓库|缓存|cache", text):
        return "data"
    # API / 服务 / 后端
    if re.search(r"\bapi\b|网关|gateway|服务|server|service|后端|微服务|接口|endpoint", text):
        return "service"
    # AI / 模型
    if re.search(r"模型|llm|gpt|claude|ai|embedding|向量化|推理|inference|agent|智能体", text):
        return "ai"
    # 消息队列 / 异步
    if re.search(r"队列|queue|kafka|rabbitmq|消息|event|事件|pub|sub|stream|流", text):
        return "queue"
    # 检索 / 搜索
    if re.search(r"检索|搜索|retriev|search|query|查询", text):
        return "search"
    # 生成 / 输出
    if re.search(r"生成|输出|回答|result|output|响应|response|返回", text):
        return "output"
    # 训练 / 学习
    if re.search(r"训练|train|微调|finetune|fine.?tun|学习|优化|loss|梯度|gradient", text):
        return "train"
    # 评估 / 指标
    if re.search(r"评估|指标|metric|eval|benchmark|测试|验证|accuracy|f1|score", text):
        return "eval"
    # 判断 / 决策
    if re.search(r"判断|决策|是否|decision", text) or kind == "decision":
        return "decision"
    # 时间 / 里程碑
    if re.search(r"时间|阶段|里程碑|milestone|year|q[1-4]|季度|phase|版本|v\d", text):
        return "time"
    # 文档 / 内容
    if re.search(r"文档|document|文件|file|内容|content|知识|章节|报告|report", text):
        return "document"
    # 网络 / 前端
    if re.search(r"前端|web|浏览器|browser|client|客户端|界面|ui|页面|app", text):
        return "client"
    # 安全 / 认证
    if re.search(r"认证|auth|token|jwt|安全|权限|permission|加密|encrypt", text):
        return "auth"
    # 监控 / 日志
    if re.search(r"监控|monitor|log|日志|告警|alert|trace|追踪|observ", text):
        return "monitor"
    return "node"


def sanitize_diagram_spec(spec: dict[str, Any], *, subtype: str = "") -> tuple[dict[str, Any], list[str], list[str]]:
    data = dict(spec or {})
    warnings: list[str] = []
    flags: list[str] = []
    changed_count = 0

    if data.get("title"):
        title = clean_title(data.get("title"))
        if title != data.get("title"):
            data["title"] = title
            changed_count += 1

    for node in data.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        label, changed = clean_label(node.get("label") or node.get("name"), max_units=14)
        if label:
            node["label"] = label
        node.setdefault("icon", icon_hint(label, str(node.get("kind") or node.get("shape") or "")))
        changed_count += int(changed)

    for stage in data.get("stages") or []:
        if isinstance(stage, dict):
            label, changed = clean_label(stage.get("label") or stage.get("name"), max_units=14)
            if label:
                stage["label"] = label
            stage.setdefault("icon", icon_hint(label, str(stage.get("kind") or "")))
            changed_count += int(changed)

    for layer in data.get("layers") or []:
        if not isinstance(layer, dict):
            continue
        label, changed = clean_label(layer.get("label"), max_units=14)
        if label:
            layer["label"] = label
        changed_count += int(changed)
        modules = []
        for module in layer.get("modules") or []:
            cleaned, module_changed = clean_label(module, max_units=18)
            if cleaned:
                modules.append(cleaned)
            changed_count += int(module_changed)
        if modules:
            layer["modules"] = modules

    for child in data.get("children") or []:
        _sanitize_tree_node(child)

    for block in data.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        label, changed = clean_label(block.get("label"), max_units=16)
        if label:
            block["label"] = label
        block.setdefault("icon", icon_hint(label))
        changed_count += int(changed)
        items = []
        for item in block.get("items") or []:
            cleaned, item_changed = clean_label(item, max_units=16)
            if cleaned:
                items.append(cleaned)
            changed_count += int(item_changed)
        block["items"] = items[:3]

    if data.get("root"):
        root, changed = clean_label(data.get("root"), max_units=18)
        data["root"] = root
        changed_count += int(changed)
    if data.get("center"):
        center, changed = clean_label(data.get("center"), max_units=18)
        data["center"] = center
        changed_count += int(changed)
    if data.get("concepts"):
        concepts = []
        for concept in data.get("concepts") or []:
            cleaned, concept_changed = clean_label(concept, max_units=18)
            if cleaned:
                concepts.append(cleaned)
            changed_count += int(concept_changed)
        data["concepts"] = concepts

    if changed_count:
        flags.append("label_hygiene")
        warnings.append(f"已清理 {changed_count} 个说明性标签片段")
    if _looks_like_generic_relation(data, subtype):
        flags.append("generic_relation_regression")
        warnings.append("结构疑似退化为中心节点+横向子节点，建议重新语义规划")
    data["diagram_subtype"] = subtype or data.get("diagram_subtype") or ""
    return data, warnings, flags


def _looks_like_generic_relation(data: dict[str, Any], subtype: str) -> bool:
    if subtype not in {"process_flow", "comparison_matrix", "infographic", "system_architecture", "rag", "agent"}:
        return False
    if data.get("columns") or data.get("dimensions") or data.get("blocks") or data.get("layers") or data.get("stages"):
        return False
    nodes = [n for n in data.get("nodes") or [] if isinstance(n, dict)]
    edges = [e for e in data.get("edges") or [] if isinstance(e, dict)]
    if len(nodes) < 3 or not edges:
        return False
    outgoing: dict[str, int] = {}
    incoming: dict[str, int] = {}
    for edge in edges:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        outgoing[src] = outgoing.get(src, 0) + 1
        incoming[dst] = incoming.get(dst, 0) + 1
    hub = max(outgoing.values(), default=0)
    return hub >= len(nodes) - 1 and sum(1 for n in nodes if incoming.get(str(n.get("id") or ""), 0)) >= len(nodes) - 1


def _sanitize_tree_node(node: Any) -> None:
    if not isinstance(node, dict):
        return
    label, _ = clean_label(node.get("label") or node.get("name"), max_units=16)
    if label:
        node["label"] = label
    node.setdefault("icon", icon_hint(label))
    for child in node.get("children") or []:
        _sanitize_tree_node(child)


def sanitize_parsed_diagram(parsed: ParsedDiagram, *, subtype: str = "") -> ParsedDiagram:
    spec, warnings, flags = sanitize_diagram_spec(parsed.parsed_spec, subtype=subtype)
    if warnings:
        spec["render_warnings"] = list(spec.get("render_warnings") or []) + warnings
    if flags:
        spec["quality_flags"] = list(spec.get("quality_flags") or []) + flags
    return ParsedDiagram(spec, parsed.source)
