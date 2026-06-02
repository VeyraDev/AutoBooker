"""RAG 架构解析。"""

from __future__ import annotations

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析 RAG 系统架构 JSON：
{{
  "title": "RAG 架构",
  "modules": [
    {{"id":"user","label":"用户查询"}},
    {{"id":"retriever","label":"检索器"}},
    {{"id":"vectorstore","label":"向量库"}},
    {{"id":"generator","label":"生成模型"}}
  ],
  "edges": [
    {{"from":"user","to":"retriever"}},
    {{"from":"retriever","to":"vectorstore"}},
    {{"from":"retriever","to":"generator"}},
    {{"from":"vectorstore","to":"generator"}}
  ]
}}
只输出 JSON。描述：{text}
"""


def _to_graph(data: dict) -> dict:
    modules = data.get("modules") or []
    edges = data.get("edges") or []
    nodes = []
    for i, m in enumerate(modules):
        if not isinstance(m, dict):
            continue
        nodes.append({
            "id": str(m.get("id") or f"m{i}"),
            "label": str(m.get("label") or "")[:24],
            "shape": "box",
            "level": 1 if i > 0 else 0,
            "column": i,
        })
    if not nodes:
        nodes = [
            {"id": "user", "label": "用户查询", "shape": "box", "level": 0, "column": 0},
            {"id": "retriever", "label": "检索器", "shape": "box", "level": 1, "column": 1},
            {"id": "vectorstore", "label": "向量库", "shape": "box", "level": 1, "column": 0},
            {"id": "generator", "label": "生成模型", "shape": "box", "level": 1, "column": 2},
        ]
        edges = [
            {"from": "user", "to": "retriever"},
            {"from": "retriever", "to": "vectorstore"},
            {"from": "retriever", "to": "generator"},
        ]
    return {
        "layout": "LR",
        "title": data.get("title") or "RAG 架构",
        "nodes": nodes,
        "edges": edges,
    }


def parse_rag(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    model = (ctx.model or settings.intent_model).strip()
    if ctx.use_llm and model:
        try:
            out = LLMClient().chat_completion(
                [{"role": "user", "content": _PROMPT.format(text=ctx.normalized_input[:2500])}],
                model=model,
                max_tokens=2048,
                temperature=0.2,
            )
            data = parse_llm_json(out)
            if isinstance(data, dict):
                return ParsedDiagram(_to_graph(data), "llm_rag")
        except Exception:
            pass
    return ParsedDiagram(_to_graph({}), "default_rag")
