"""process_flow 控制流语义：nodes/edges 格式、校验、规则推断、布局层推导。"""

from __future__ import annotations

import re
from typing import Any

FLOW_NODE_KINDS = frozenset({
    "start", "end", "task", "decision",
    "parallel_split", "parallel_join",
    "subprocess", "swimlane",
})
FLOW_EDGE_KINDS = frozenset({"default", "loop_back"})

_PARALLEL_TEXT = re.compile(r"并行|两支|两个.{0,6}分支|分叉|同时")
_JOIN_TEXT = re.compile(r"汇合|共同进入|汇聚|合并后|汇合后")
_DECISION_TEXT = re.compile(r"若|如果|否则|不达标|未达标|失败|通过|未通过|是否")
_LOOP_TEXT = re.compile(r"返回|重试|重新|回到|再次|回路|反馈")
_PREP_RE = re.compile(r"数据准备|准备数据|预处理")
_TRAIN_RE = re.compile(r"训练")


def _short(text: Any, limit: int = 22) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。")
    return raw[:limit].strip(" ：:，,。")


def _clean_task_label(text: str) -> str:
    label = _short(text, 22)
    label = re.sub(r"^(?:从|经过|最终|最后|然后|接着|再到|汇合后|汇合后进行|进行)", "", label).strip()
    label = re.sub(r"(?:两个|两条|多个)?并行分支$", "", label).strip()
    return _short(label.strip(" ：:，,。"), 12)


def _flow_nodes(native: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for n in (native.get("nodes") or []) if isinstance(n, dict) and str(n.get("id") or "").strip()]


def _flow_edges(native: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in list(native.get("edges") or []) + list(native.get("feedback") or []):
        if not isinstance(raw, dict):
            continue
        edge = dict(raw)
        if edge in (native.get("feedback") or []):
            edge.setdefault("kind", "loop_back")
        out.append(edge)
    return out


def _node_by_kind(nodes: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [n for n in nodes if str(n.get("kind") or "").lower() == kind]


def _task_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [n for n in nodes if str(n.get("kind") or "").lower() == "task"]


def _loop_back_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        e for e in edges
        if str(e.get("kind") or "").lower() == "loop_back"
        or str(e.get("label") or "") in {"不达标", "返回", "重试", "未达标", "失败"}
    ]


def infer_process_flow_from_text(text: str) -> dict[str, Any] | None:
    """从描述推断标准控制流图（含 parallel_split/join、decision、loop_back）。"""
    if not (_PARALLEL_TEXT.search(text) or _JOIN_TEXT.search(text)):
        return None
    branch_match = re.search(
        r"(?:包含|包括|有)?([^，,。；;]+?)、([^，,。；;]+?)(?:两个|两条|多个)?并行分支",
        text,
    )
    merge_match = re.search(r"汇合后(?:进行)?([^，,。；;]+)", text)
    eval_match = re.search(r"(?:最后|最终)([^，,。；;]+)", text)
    feedback_match = re.search(
        r"若([^，,。；;]+?)则返回([^，,。；;]+?)(?:步骤|阶段|环节)?(?:，|,|。|$)",
        text,
    )
    if not branch_match or not merge_match:
        return None

    left = _clean_task_label(branch_match.group(1))
    right = _clean_task_label(branch_match.group(2))
    merge = _clean_task_label(merge_match.group(1))
    eval_label = _clean_task_label(eval_match.group(1)) if eval_match else "评估指标"
    return_target = _clean_task_label(feedback_match.group(2)) if feedback_match else left
    return_id = "data" if "数据" in return_target or return_target == left else "data"

    native: dict[str, Any] = {
        "type": "process_flow",
        "nodes": [
            {"id": "start", "label": "开始", "kind": "start"},
            {"id": "split1", "label": "并行开始", "kind": "parallel_split"},
            {"id": "data", "label": left or "数据准备", "kind": "task"},
            {"id": "model", "label": right or "模型选择", "kind": "task"},
            {"id": "join1", "label": "汇合", "kind": "parallel_join"},
            {"id": "train", "label": merge or "训练", "kind": "task"},
            {"id": "eval", "label": eval_label, "kind": "task"},
            {"id": "decision1", "label": "是否达标", "kind": "decision"},
            {"id": "end", "label": "结束", "kind": "end"},
        ],
        "edges": [
            {"from": "start", "to": "split1"},
            {"from": "split1", "to": "data"},
            {"from": "split1", "to": "model"},
            {"from": "data", "to": "join1"},
            {"from": "model", "to": "join1"},
            {"from": "join1", "to": "train"},
            {"from": "train", "to": "eval"},
            {"from": "eval", "to": "decision1"},
            {"from": "decision1", "to": "end", "label": "达标"},
            {"from": "decision1", "to": return_id, "label": "不达标", "kind": "loop_back"},
        ],
    }
    return native


def _infer_loop_feedback_from_text(text: str, stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从描述推断 feedback / loop_back 边（grammar stages 格式）。"""
    if not _LOOP_TEXT.search(text) or len(stages) < 2:
        return []

    target_label: str | None = None
    patterns = (
        r"若[^，,。；;]+?则返回([^，,。；;]+?)(?:步骤|阶段|环节)?",
        r"未达标[^，,。；;]*?(?:返回|回到|重新)([^，,。；;]+?)(?:步骤|阶段|环节)?",
        r"(?:不达标|未通过|失败)[^，,。；;]*?(?:返回|回到|重新)([^，,。；;]+?)(?:步骤|阶段|环节)?",
        r"(?:返回|回到|重新)([^，,。；;]+?)(?:步骤|阶段|环节)",
    )
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            target_label = _clean_task_label(match.group(1))
            break
    if not target_label:
        return []

    decision_id: str | None = None
    for i, stage in enumerate(stages):
        sid = str(stage.get("id") or f"s{i}")
        if str(stage.get("kind") or "") == "decision":
            decision_id = sid
            break
        if re.search(r"是否|达标|判断", str(stage.get("label") or "")):
            decision_id = sid
            break
    if not decision_id:
        decision_id = str(stages[-1].get("id") or f"s{len(stages) - 1}")

    target_id: str | None = None
    for i, stage in enumerate(stages):
        sid = str(stage.get("id") or f"s{i}")
        label = _clean_task_label(str(stage.get("label") or ""))
        if label == target_label or target_label in label or label in target_label:
            target_id = sid
            break
    if not target_id:
        target_id = str(stages[0].get("id") or "s0")

    if decision_id and target_id and decision_id != target_id:
        return [{"from": decision_id, "to": target_id, "label": "不达标"}]
    return []


def infer_linear_flow_from_text(text: str) -> dict[str, Any] | None:
    """线性流程（无并行关键词）→ 控制流图。"""
    from app.services.figures.parse.pipeline import _rule_stages

    stages = _rule_stages(text)
    if len(stages) < 2:
        return None
    feedback = _infer_loop_feedback_from_text(text, stages)
    return _linear_steps_to_control_flow(stages, [], feedback)


def infer_any_flow_from_text(text: str) -> dict[str, Any] | None:
    return infer_process_flow_from_text(text) or infer_linear_flow_from_text(text)


def _control_flow_to_grammar_spec(native: dict[str, Any], title: str, text: str) -> dict[str, Any] | None:
    """控制流 native → grammar spec（保留 loop_back / feedback）。"""
    from app.services.figures.parse.pipeline import _to_graph

    stages = infer_grammar_stages_from_text(text)
    if not stages:
        return None

    label_to_stage = {str(stage.get("label") or ""): str(stage["id"]) for stage in stages}
    id_to_stage: dict[str, str] = {}
    for node in _flow_nodes(native):
        label = str(node.get("label") or "")
        if label in label_to_stage:
            id_to_stage[str(node["id"])] = label_to_stage[label]

    feedback: list[dict[str, Any]] = []
    for edge in _flow_edges(native):
        is_loop = (
            str(edge.get("kind") or "").lower() == "loop_back"
            or str(edge.get("label") or "") in {"不达标", "返回", "重试", "未达标", "失败"}
        )
        if not is_loop:
            continue
        src = id_to_stage.get(str(edge.get("from") or ""))
        tgt = id_to_stage.get(str(edge.get("to") or ""))
        if src and tgt:
            feedback.append({
                "from": src,
                "to": tgt,
                "label": str(edge.get("label") or "不达标"),
            })
    if not feedback:
        feedback = _infer_loop_feedback_from_text(text, stages)
    return _to_graph(title, stages, [], feedback)


def repair_grammar_flow_spec(spec: dict[str, Any], text: str) -> dict[str, Any] | None:
    """Grammar LLM 未通过时，用规则重建 stages/nodes spec。"""
    from app.services.figures.parse.pipeline import _rule_stages, _to_graph

    title = str(spec.get("title") or "流程图")[:24]

    native = infer_any_flow_from_text(text)
    if native:
        repaired = repair_process_flow_native(native, text)
        if not flow_semantic_critic(repaired, text):
            grammar = _control_flow_to_grammar_spec(repaired, title, text)
            if grammar:
                return grammar

    stages = infer_grammar_stages_from_text(text) or _rule_stages(text)
    if not stages or len(stages) < 2:
        return None

    feedback = _infer_loop_feedback_from_text(text, stages)
    return _to_graph(title, stages, [], feedback)


def flow_semantic_critic(native: dict[str, Any], text: str) -> list[str]:
    """Flow Semantic Critic：控制流完整性（不负责布局）。"""
    issues: list[str] = []
    nodes = _flow_nodes(native)
    edges = _flow_edges(native)

    if not nodes:
        issues.append("flow_missing_nodes")
        if native.get("steps"):
            issues.append("flow_legacy_steps_format")
        return issues
    if len(edges) < 1:
        issues.append("flow_missing_edges")

    ids = {str(n["id"]) for n in nodes}
    for edge in edges:
        src, tgt = str(edge.get("from") or ""), str(edge.get("to") or "")
        if src not in ids or tgt not in ids:
            issues.append("flow_edge_invalid_endpoint")
            break

    tasks = _task_nodes(nodes)
    splits = _node_by_kind(nodes, "parallel_split")
    joins = _node_by_kind(nodes, "parallel_join")
    decisions = _node_by_kind(nodes, "decision")
    loops = _loop_back_edges(edges)

    # 1. 并列任务无 parallel_split
    if _PARALLEL_TEXT.search(text) or len(tasks) >= 2:
        if _PARALLEL_TEXT.search(text) and not splits:
            parallel_tasks = _detect_parallel_tasks_from_edges(nodes, edges)
            if len(parallel_tasks) >= 2 or _PARALLEL_TEXT.search(text):
                issues.append("flow_missing_parallel_split")
        elif len(tasks) >= 2 and not splits and _PARALLEL_TEXT.search(text):
            issues.append("flow_missing_parallel_split")

    # 2. 汇合语义无 parallel_join
    if _JOIN_TEXT.search(text) and not joins:
        if splits or _PARALLEL_TEXT.search(text):
            issues.append("flow_missing_parallel_join")

    # 3. 决策语义无 decision 节点
    if _DECISION_TEXT.search(text) and not decisions:
        issues.append("flow_missing_decision_node")

    # 4. 回环语义无 loop_back
    if _LOOP_TEXT.search(text) and not loops:
        issues.append("flow_missing_loop_back_edge")

    # 5. loop_back 是否指回前置节点
    layer_of = derive_flow_layers(native)
    for edge in loops:
        src, tgt = str(edge.get("from") or ""), str(edge.get("to") or "")
        if src not in layer_of or tgt not in layer_of:
            issues.append("flow_loop_back_invalid_target")
            continue
        if layer_of.get(tgt, 0) >= layer_of.get(src, 0):
            issues.append("flow_loop_back_not_backward")

    for node in nodes:
        kind = str(node.get("kind") or "")
        if kind and kind not in FLOW_NODE_KINDS:
            issues.append(f"flow_unknown_node_kind:{kind}")
        label = str(node.get("label") or "")
        if re.search(r"level|column|坐标|布局", label, re.I):
            issues.append("flow_layout_leaked_into_semantic")

    return list(dict.fromkeys(issues))


def _detect_parallel_tasks_from_edges(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[str]:
    """同一前驱分出 ≥2 条边到 task → 视为并列任务。"""
    preds: dict[str, list[str]] = {}
    task_ids = {str(n["id"]) for n in nodes if str(n.get("kind") or "") == "task"}
    for edge in edges:
        if str(edge.get("kind") or "").lower() == "loop_back":
            continue
        src, tgt = str(edge.get("from") or ""), str(edge.get("to") or "")
        if tgt in task_ids:
            preds.setdefault(src, []).append(tgt)
    parallel: list[str] = []
    for tgts in preds.values():
        if len(tgts) >= 2:
            parallel.extend(tgts)
    return parallel


def derive_flow_layers(native: dict[str, Any]) -> dict[str, int]:
    """从控制流图推导布局层（忽略 loop_back，供 layout 使用）。"""
    nodes = _flow_nodes(native)
    if not nodes:
        return {}
    edges = [e for e in _flow_edges(native) if str(e.get("kind") or "").lower() != "loop_back"]
    node_map = {str(n["id"]): n for n in nodes}
    ids = list(node_map.keys())

    preds: dict[str, list[str]] = {nid: [] for nid in ids}
    succs: dict[str, list[str]] = {nid: [] for nid in ids}
    for edge in edges:
        src, tgt = str(edge.get("from") or ""), str(edge.get("to") or "")
        if src in succs and tgt in preds and src != tgt:
            succs[src].append(tgt)
            preds[tgt].append(src)

    layers: dict[str, int] = {}
    roots = [nid for nid in ids if not preds[nid]] or [ids[0]]
    for root in roots:
        layers.setdefault(root, 0)

    changed = True
    while changed:
        changed = False
        for nid in ids:
            kind = str(node_map[nid].get("kind") or "")
            if not preds[nid]:
                if nid not in layers:
                    layers[nid] = 0
                    changed = True
                continue
            if not all(p in layers for p in preds[nid]):
                continue
            if kind == "parallel_join":
                new_layer = max(layers[p] for p in preds[nid]) + 1
            elif kind == "task" and any(
                str(node_map.get(p, {}).get("kind") or "") == "parallel_split" for p in preds[nid]
            ):
                new_layer = max(layers[p] for p in preds[nid]) + 1
            else:
                new_layer = max(layers[p] for p in preds[nid]) + 1
            if layers.get(nid) != new_layer:
                layers[nid] = new_layer
                changed = True

        for nid in ids:
            if str(node_map[nid].get("kind") or "") != "parallel_split":
                continue
            if nid not in layers:
                continue
            split_layer = layers[nid]
            for tgt in succs[nid]:
                if str(node_map.get(tgt, {}).get("kind") or "") == "task":
                    task_layer = split_layer + 1
                    if layers.get(tgt) != task_layer:
                        layers[tgt] = task_layer
                        changed = True

    for nid in ids:
        layers.setdefault(nid, 0)
    return layers


def derive_flow_columns(native: dict[str, Any], layers: dict[str, int]) -> dict[str, int]:
    """同层并列 task（来自同一 parallel_split）分配 column。"""
    nodes = _flow_nodes(native)
    edges = [e for e in _flow_edges(native) if str(e.get("kind") or "").lower() != "loop_back"]
    node_map = {str(n["id"]): n for n in nodes}
    columns: dict[str, int] = {}
    assigned: set[str] = set()

    for edge in edges:
        src, tgt = str(edge.get("from") or ""), str(edge.get("to") or "")
        if str(node_map.get(src, {}).get("kind") or "") != "parallel_split":
            continue
        if str(node_map.get(tgt, {}).get("kind") or "") != "task":
            continue
        split_tasks = [
            str(e.get("to") or "")
            for e in edges
            if str(e.get("from") or "") == src
            and str(node_map.get(str(e.get("to") or ""), {}).get("kind") or "") == "task"
        ]
        for i, tid in enumerate(sorted(split_tasks)):
            columns[tid] = i
            assigned.add(tid)

    by_layer: dict[int, list[str]] = {}
    for nid, lvl in layers.items():
        by_layer.setdefault(lvl, []).append(nid)
    for nids in by_layer.values():
        col = 0
        for nid in sorted(nids):
            if nid not in assigned:
                columns[nid] = col
                col += 1
    return columns


def coerce_process_flow_native(native: dict[str, Any], text: str = "") -> dict[str, Any]:
    """统一为 nodes/edges 控制流格式；淘汰 steps/feedback 旧格式。"""
    if not native:
        return {"type": "process_flow", "nodes": [], "edges": []}

    out = dict(native)
    out["type"] = "process_flow"

    if _flow_nodes(out) and _flow_edges(out):
        return out

    if text.strip():
        inferred = infer_any_flow_from_text(text)
        if inferred:
            return inferred

    # legacy steps → 尝试推断，否则线性降级
    steps = [s for s in (out.get("steps") or []) if isinstance(s, dict)]
    if steps:
        inferred = infer_process_flow_from_text(text) if text.strip() else None
        if inferred:
            return inferred
        return _linear_steps_to_control_flow(steps, out.get("edges") or [], out.get("feedback") or [])

    return {"type": "process_flow", "nodes": [], "edges": []}


def _linear_steps_to_control_flow(
    steps: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
) -> dict[str, Any]:
    """最后兜底：线性 steps 转最简控制流（无并行 split/join）。"""
    nodes: list[dict[str, Any]] = [{"id": "start", "label": "开始", "kind": "start"}]
    id_map: dict[str, str] = {}
    for i, step in enumerate(steps):
        sid = str(step.get("id") or f"s{i}")
        kind = str(step.get("kind") or "task").lower()
        if kind in {"parallel", "branch"}:
            kind = "task"
        elif kind == "decision" or re.search(r"是否", str(step.get("label") or "")):
            kind = "decision"
        elif kind in {"output"}:
            kind = "end"
        else:
            kind = "task"
        nodes.append({"id": sid, "label": str(step.get("label") or f"步骤{i+1}"), "kind": kind})
        id_map[sid] = sid
    nodes.append({"id": "end", "label": "结束", "kind": "end"})

    flow_edges: list[dict[str, Any]] = []
    if edges:
        for e in edges:
            if isinstance(e, dict):
                flow_edges.append({
                    "from": str(e.get("from") or ""),
                    "to": str(e.get("to") or ""),
                    "label": str(e.get("label") or ""),
                    "kind": "loop_back" if str(e.get("label") or "") in {"不达标", "返回", "重试"} else "default",
                })
    else:
        ordered = ["start"] + [str(s.get("id") or f"s{i}") for i, s in enumerate(steps)] + ["end"]
        for i in range(len(ordered) - 1):
            flow_edges.append({"from": ordered[i], "to": ordered[i + 1]})

    for fb in feedback:
        if isinstance(fb, dict):
            flow_edges.append({
                "from": str(fb.get("from") or ""),
                "to": str(fb.get("to") or ""),
                "label": str(fb.get("label") or "不达标"),
                "kind": "loop_back",
            })

    return {"type": "process_flow", "nodes": nodes, "edges": flow_edges}


def needs_process_flow_repair(native: dict[str, Any], text: str) -> bool:
    coerced = coerce_process_flow_native(native, text)
    if not _flow_nodes(coerced) or not _flow_edges(coerced):
        return True
    return bool(flow_semantic_critic(coerced, text))


def repair_process_flow_native(native: dict[str, Any], text: str) -> dict[str, Any]:
    if text.strip():
        inferred = infer_any_flow_from_text(text)
        if inferred:
            return inferred
    return coerce_process_flow_native(native, text)


def is_usable_process_flow(native: dict[str, Any]) -> bool:
    nodes = _flow_nodes(native)
    edges = _flow_edges(native)
    if len(nodes) < 2 or len(edges) < 1:
        return False
    if native.get("steps") and not native.get("nodes"):
        return False
    return True


def process_flow_structure_issues(native: dict[str, Any], text: str) -> list[str]:
    coerced = coerce_process_flow_native(native, text)
    return flow_semantic_critic(coerced, text)


def infer_grammar_stages_from_text(text: str) -> list[dict[str, Any]] | None:
    """Grammar parser 兼容：控制流 → stages（level/column 仅用于 grammar 布局 hints）。"""
    cf = infer_process_flow_from_text(text)
    if not cf:
        return None
    layers = derive_flow_layers(cf)
    columns = derive_flow_columns(cf, layers)
    node_map = {str(n["id"]): n for n in _flow_nodes(cf)}
    edges = [e for e in _flow_edges(cf) if str(e.get("kind") or "").lower() != "loop_back"]

    split_to_tasks: dict[str, list[str]] = {}
    for edge in edges:
        src, tgt = str(edge.get("from") or ""), str(edge.get("to") or "")
        if str(node_map.get(src, {}).get("kind") or "") == "parallel_split":
            if str(node_map.get(tgt, {}).get("kind") or "") == "task":
                split_to_tasks.setdefault(src, []).append(tgt)

    raw_stages: list[dict[str, Any]] = []
    for nid, node in node_map.items():
        kind = str(node.get("kind") or "")
        if kind in {"start", "end", "parallel_split", "parallel_join", "swimlane", "subprocess"}:
            continue
        stage_kind = "decision" if kind == "decision" else "step"
        for tasks in split_to_tasks.values():
            if nid in tasks and len(tasks) >= 2:
                stage_kind = "parallel"
                break
        raw_stages.append({
            "label": str(node.get("label") or nid),
            "kind": stage_kind,
            "level": layers.get(nid, 0),
            "column": columns.get(nid, 0),
            "_nid": nid,
        })
    if not raw_stages:
        return None
    raw_stages.sort(key=lambda s: (int(s["level"]), int(s["column"])))
    compacted: list[dict[str, Any]] = []
    lvl = 0
    i = 0
    while i < len(raw_stages):
        if raw_stages[i]["kind"] == "parallel":
            j = i
            base_layer = raw_stages[i]["level"]
            while j < len(raw_stages) and raw_stages[j]["kind"] == "parallel" and raw_stages[j]["level"] == base_layer:
                compacted.append({**raw_stages[j], "level": lvl, "column": raw_stages[j]["column"]})
                j += 1
            i = j
            lvl += 1
        else:
            compacted.append({**raw_stages[i], "level": lvl, "column": 0})
            i += 1
            lvl += 1
    return [
        {
            "id": f"s{idx}",
            "label": stage["label"],
            "kind": stage["kind"],
            "level": stage["level"],
            "column": stage["column"],
        }
        for idx, stage in enumerate(compacted)
    ]
