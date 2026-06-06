"""意图证据打分。"""

from __future__ import annotations

import re
from typing import Any

_ARCH = re.compile(r"架构|服务|网关|微服务|模块|组件|系统|API|集群|部署")
_FLOW = re.compile(r"流程|步骤|阶段|顺序|首先|然后|接着|最后|审批|注册")
_COMPARE = re.compile(r"对比|比较|优劣|vs|VS|差异|矩阵")
_TIMELINE = re.compile(r"时间线|里程碑|路线图|roadmap|季度|年份")
_TAXONOMY = re.compile(r"分类|体系|层次|树形|知识图谱|taxonomy")
_TRANSFORMER = re.compile(r"Transformer|注意力|encoder|decoder|微调|训练|LoRA")
_RAG = re.compile(r"RAG|检索增强|向量库|embedding|知识库")
_AGENT = re.compile(r"Agent|智能体|工具调用|规划|记忆")


def score_candidate_diagrams(text: str) -> list[dict[str, Any]]:
    t = text or ""
    scores: dict[str, float] = {
        "architecture": 0.0,
        "flowchart": 0.0,
        "comparison": 0.0,
        "timeline": 0.0,
        "taxonomy": 0.0,
        "transformer": 0.0,
        "rag": 0.0,
        "agent": 0.0,
    }
    reasons: dict[str, str] = {}

    if _ARCH.search(t):
        scores["architecture"] += 0.55
        reasons["architecture"] = "系统/服务/架构关键词"
    if _FLOW.search(t):
        scores["flowchart"] += 0.5
        reasons["flowchart"] = "流程/步骤关键词"
    if _COMPARE.search(t):
        scores["comparison"] += 0.45
        reasons["comparison"] = "对比关键词"
    if _TIMELINE.search(t):
        scores["timeline"] += 0.45
        reasons["timeline"] = "时间线关键词"
    if _TAXONOMY.search(t):
        scores["taxonomy"] += 0.4
        reasons["taxonomy"] = "分类/体系关键词"
    if _TRANSFORMER.search(t):
        scores["transformer"] += 0.5
        scores["flowchart"] += 0.2
        reasons["transformer"] = "大模型/微调关键词"
    if _RAG.search(t):
        scores["rag"] += 0.55
        scores["architecture"] += 0.15
        reasons["rag"] = "RAG/检索关键词"
    if _AGENT.search(t):
        scores["agent"] += 0.5
        reasons["agent"] = "Agent 关键词"

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    out: list[dict[str, Any]] = []
    for dtype, score in ranked:
        if score < 0.25:
            continue
        out.append({"type": dtype, "score": round(min(0.99, score), 2), "reason": reasons.get(dtype, dtype)})
    if not out:
        out.append({"type": "flowchart", "score": 0.4, "reason": "默认流程图"})
    return out[:4]
