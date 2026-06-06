"""Diagram Intent LLM 分类（仅 family + subtype，不抽结构）。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.intent.taxonomy import (
    FAMILY_DEFAULT_SUBTYPE,
    canonical_subtype,
    diagram_type_to_subtype,
    subtype_to_diagram_type,
)
from app.services.figures.prompts import format_prompt, load_prompt
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_INTENT_PROMPT_LEGACY = """你是图书配图的语义意图识别模块。只判断图形族与细分类，不要输出 nodes/edges/prompt。

你必须根据“作者真正想画的图形语法”分类，而不是按领域名词套模板。例如：
- “RAG pipeline：提问→向量化→检索→生成”是 workflow/process_flow，不是 rag 架构。
- “RAG 系统架构：用户、检索器、向量库、LLM 的模块关系”才是 architecture/rag 或 system_architecture。
- “Attention 权重矩阵 / Q-K scores / mask / softmax 可视化”是 matrix/attention_matrix。
- “Transformer 编码器-解码器堆叠结构”才是 transformer。
- “A、B、C 的差异/优劣/维度比较”是 comparison_matrix。
- “章节核心要点、多个信息块、图标化总结”是 infographic。

必须只输出 JSON：
{{
  "diagram_family": "architecture|decision|workflow|matrix|knowledge|timeline|organization|illustration|data",
  "diagram_subtype": "concept_diagram|mechanism_diagram|process_flow|system_architecture|data_visualization|chart|comparison_matrix|taxonomy_map|timeline_roadmap|decision_tree|transformer|rag|agent|swot|attention_matrix|scene_illustration|infographic|org_chart",
  "confidence": 0.0,
  "title": "图题建议，不超过 24 个中文字符"
}}

分类规则：
1. 有真实数值/统计趋势/占比，并且用户要图表 → data / chart。
2. 操作步骤、用户路径、从 A 到 B 的流程 → workflow / process_flow。
3. 系统模块、层级、服务、数据库、Agent/RAG 架构 → architecture / system_architecture；明确 RAG → rag；明确 Transformer 编码器解码器 → transformer。
4. 模型/算法/机制内部如何运作 → knowledge / mechanism_diagram。
5. 两个或多个对象优劣/差异 → matrix / comparison_matrix；SWOT → swot。
6. 分类体系、知识图谱、能力地图、思维导图 → knowledge / taxonomy_map。
7. 时间演进、路线图、学习路径 → timeline / timeline_roadmap。
8. 帮读者判断/选择 → decision / decision_tree。
9. 章节总结、知识总结、多个信息块组合 → knowledge / infographic。
10. 只有具象场景、人物、氛围、封面感时 → illustration / scene_illustration。
11. 抽象关系解释，且不属于以上情况 → knowledge / concept_diagram。

重要：concept_diagram、infographic、comparison_matrix、taxonomy_map 都不是场景插画；不要因为出现“图”字就判为 illustration。
重要：title 只给短图题，不要复制“完整、左侧、右侧、用箭头连接、展示以下”等版式说明。

语义净化规则（必须严格执行）：
- 描述中出现"X连接前N个/所有Y""X通过Z通知Y""X包含N个模块"等聚合关系句，这些句子描述的是 edges/connections，不是节点名。不要将整句或其任何片段写进 diagram_subtype 或 title。
- title 只给语义图题（如"微服务架构""用户注册流程"），禁止包含"共X个""前N个""通过消息队列"等关系描述词。
- 若描述中明显是"说明如何布局"（如"用方框和箭头展示""左边是A右边是B""用箭头连接以下步骤"），这是版式说明，不影响 diagram_family/subtype 判断，直接忽略。

【diagram_type 与 title 约束】
- title 是图的"名字"，不是图的"描述"。只写 4-8 字的名词短语（"用户注册流程""微服务架构""RAG 调用链"）。
- 禁止在 title 中出现：动词（连接/通过/展示）、计数词（三个/前两个/共五个）、位置词（左侧/右边）。
- 若描述中同时出现"步骤/流程/阶段"和"模块/服务/架构"，优先判断用户真正想看的是哪一个：
    如果描述以"A→B→C"或"先做X再做Y"为主 → workflow/process_flow
    如果描述以"X包含Y Z，Y调用Z"为主 → architecture/system_architecture
- "订单服务通过消息队列异步通知支付服务"是一条 relation，不影响 diagram_type 判断，不进 title。

书型：{book_type} / 风格：{style_type}
章节：{chapter_title}
用户补充：{user_hint}
描述：
{normalized_input}
"""


def classify_diagram_intent(ctx: PipelineContext) -> DiagramIntent | None:
    model = (ctx.model or settings.intent_model).strip()
    if not model or not ctx.normalized_input.strip():
        return None
    try:
        prompt = format_prompt(
            "intent",
            book_type=ctx.book_type or "nonfiction",
            style_type=ctx.style_type or "general",
            chapter_title=ctx.chapter_title or "（无）",
            user_hint=ctx.user_hint or "（无）",
            normalized_input=ctx.normalized_input[:2500],
        )
    except OSError:
        prompt = _INTENT_PROMPT_LEGACY.format(
            book_type=ctx.book_type or "nonfiction",
            style_type=ctx.style_type or "general",
            chapter_title=ctx.chapter_title or "（无）",
            user_hint=ctx.user_hint or "（无）",
            normalized_input=ctx.normalized_input[:2500],
        )
    try:
        client = LLMClient()
        out = client.chat_completion(
            [
                {"role": "system", "content": "只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            model=model,
            max_tokens=512,
            temperature=0.05,
        )
        data = parse_llm_json(out)
        return _sanitize_intent(data)
    except Exception as e:
        logger.warning("diagram intent LLM failed: %s", e)
        return None


def _sanitize_intent(data: dict[str, Any]) -> DiagramIntent | None:
    family = str(data.get("diagram_family") or "").strip().lower()
    diagram_type = str(data.get("diagram_type") or "").strip().lower()
    subtype = canonical_subtype(str(data.get("diagram_subtype") or "").strip().lower())
    if diagram_type and not subtype:
        subtype = diagram_type_to_subtype(diagram_type)
    if not family:
        return None
    if not subtype:
        subtype = FAMILY_DEFAULT_SUBTYPE.get(family, "concept_diagram")
    if not diagram_type:
        diagram_type = subtype_to_diagram_type(subtype)
    if subtype == "data_visualization":
        subtype = "chart"
    try:
        conf = float(data.get("confidence", 0.7))
    except (TypeError, ValueError):
        conf = 0.7
    title = str(data.get("title") or "").strip()
    if len(title) > 60:
        title = title[:60] + "…"
    reason = str(data.get("reason") or "").strip()
    fallback_allowed = bool(data.get("fallback_allowed", True))
    return DiagramIntent(
        family,
        subtype,
        max(0.0, min(1.0, conf)),
        "llm",
        title,
        diagram_type=diagram_type,
        reason=reason,
        fallback_allowed=fallback_allowed,
    )
