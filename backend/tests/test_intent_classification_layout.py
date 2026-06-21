"""分类候选注册表与布局策略回归。"""

from __future__ import annotations

from app.services.figures.intent.candidate_registry import (
    resolve_best_candidate,
    resolved_to_intent,
)
from app.services.figures.intent.resolve import intent_from_understanding, resolve_intent_unified
from app.services.figures.intent.taxonomy import subtype_to_diagram_type
from app.services.figures.layout.policies import get_layout_policy, select_strategy_for_subtype
from app.services.figures.parse.chart_data import parse_chart_data_rules
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext


def test_bar_chart_alias_candidate_is_not_backend_mapped():
    ctx = PipelineContext(
        description="柱状图",
        normalized_input="柱状图展示五种LLM在MMLU基准上的得分，GPT-4得分86%，Claude-3得分85%",
    )
    understanding = {
        "goal": "show_comparison",
        "confidence": 0.98,
        "candidate_diagrams": [{"type": "bar_chart", "score": 0.95, "reason": "柱状图"}],
    }
    intent = intent_from_understanding(understanding, ctx)
    assert intent is None


def test_line_chart_alias_candidate_is_not_backend_mapped():
    ctx = PipelineContext(
        description="折线图",
        normalized_input="折线图展示训练loss曲线，X轴为训练步数1000到10000，Y轴为loss值",
    )
    understanding = {
        "goal": "illustrate_concept",
        "confidence": 0.9,
        "candidate_diagrams": [{"type": "line_chart", "score": 0.95, "reason": "折线图"}],
    }
    intent = intent_from_understanding(understanding, ctx)
    assert intent is None


def test_numeric_text_without_chart_candidate_follows_llm_goal():
    text = "市场份额：企业服务35%，医疗健康20%，教育18%"
    resolved = resolve_best_candidate([], text=text, goal="show_comparison")
    assert resolved is None


def test_scene_from_llm_candidate_not_keyword_rules():
    text = "一位工程师在暗色主题的多屏工作站前调试AI模型"
    resolved = resolve_best_candidate(
        [{"type": "scene_illustration", "score": 0.88, "reason": "场景插画"}],
        text=text,
        goal="illustrate_scene",
    )
    assert resolved is not None
    assert resolved.family == "illustration"
    assert resolved.subtype == "scene_illustration"


def test_process_flow_prefers_tb_layout_policy():
    policy = get_layout_policy("process_flow")
    strategy = select_strategy_for_subtype(
        subtype="process_flow",
        metrics={"node_count": 5, "is_linear_chain": True, "has_decision": False},
    )
    assert strategy == "TB"
    assert strategy in policy.strategies


def test_timeline_long_chain_prefers_snake_over_wide_lr():
    strategy = select_strategy_for_subtype(
        subtype="timeline_roadmap",
        metrics={"node_count": 8, "is_linear_chain": True, "has_decision": False},
    )
    assert strategy == "snake"


def test_chart_diagram_type_not_matrix():
    assert subtype_to_diagram_type("chart") == "chart"


def test_chart_rule_extract_percentages():
    ctx = PipelineContext(
        description="饼图",
        normalized_input="饼图展示市场份额，企业服务占35%，医疗健康占20%，教育占18%",
    )
    parsed = parse_chart_data_rules(ctx, DiagramIntent("data", "chart", 0.9, "test", "份额"))
    assert parsed.parsed_spec["chart_type"] == "pie"
    assert len(parsed.parsed_spec["values"]) >= 2


def test_resolve_intent_unified_from_llm_candidates():
    ctx = PipelineContext(
        description="流程",
        normalized_input="用户注册流程：填写表单、邮件验证、完善资料、完成注册",
        use_llm=True,
    )
    understanding = {
        "goal": "show_workflow",
        "confidence": 0.8,
        "candidate_diagrams": [{"type": "process_flow", "score": 0.86, "reason": "流程"}],
    }
    intent = resolve_intent_unified(ctx, understanding)
    assert intent.diagram_family == "workflow"
    assert intent.diagram_subtype == "process_flow"


def test_rag_architecture_uses_exact_system_architecture_type():
    ctx = PipelineContext(
        description="RAG架构",
        normalized_input="RAG系统架构：用户查询、检索器、向量库、大模型",
    )
    understanding = {
        "goal": "show_system_architecture",
        "confidence": 0.9,
        "candidate_diagrams": [{"type": "system_architecture", "score": 0.88, "reason": "RAG"}],
    }
    intent = intent_from_understanding(understanding, ctx)
    assert intent is not None
    assert intent.diagram_subtype == "system_architecture"
    assert intent.diagram_family == "architecture"


def test_resolved_to_intent_sets_chart_diagram_type():
    from app.services.figures.intent.candidate_registry import ResolvedCandidate

    intent = resolved_to_intent(
        ResolvedCandidate("data", "chart", 0.9, "test", "柱状图", "bar_chart"),
        title="得分对比",
    )
    assert intent.diagram_type == "chart"
