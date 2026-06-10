"""Grammar parser prompt 不得因 JSON 花括号导致 format KeyError。"""

from __future__ import annotations

import importlib

import pytest

from app.services.figures.parse.llm_helpers import substitute_prompt_text
from app.services.figures.schemas.diagram import PipelineContext


@pytest.mark.parametrize(
    "module_name",
    [
        "pipeline",
        "mechanism",
        "architecture",
        "comparison",
        "timeline",
        "infographic",
        "taxonomy",
        "network",
        "decision_tree",
        "swot",
        "chart_data",
    ],
)
def test_parser_prompt_substitute_text(module_name: str):
    mod = importlib.import_module(f"app.services.figures.parse.{module_name}")
    prompt = getattr(mod, "_PROMPT", None)
    assert prompt, f"{module_name} missing _PROMPT"
    ctx = PipelineContext(description="", normalized_input="测试描述文本", use_llm=True)
    out = substitute_prompt_text(prompt, ctx)
    assert "测试描述文本" in out
    assert "{text}" not in out


def test_parse_pipeline_does_not_fallback_on_prompt_error(monkeypatch):
    """LLM 可用时 parse_pipeline 不应因 prompt 异常落入 fallback_concept。"""
    from app.services.figures.parse.pipeline import parse_pipeline
    from app.services.figures.schemas.diagram import DiagramIntent

    called = {"n": 0}

    def fake_llm(ctx, prompt, **kwargs):
        called["n"] += 1
        return {
            "title": "微调流程",
            "stages": [
                {"id": "s0", "label": "数据准备", "kind": "parallel", "level": 0, "column": 0},
                {"id": "s1", "label": "模型选择", "kind": "parallel", "level": 0, "column": 1},
                {"id": "s2", "label": "训练", "kind": "step", "level": 1, "column": 0},
                {"id": "s3", "label": "评估指标", "kind": "step", "level": 2, "column": 0},
                {"id": "s4", "label": "是否达标", "kind": "decision", "level": 3, "column": 0},
            ],
            "edges": [
                {"from": "s0", "to": "s2"},
                {"from": "s1", "to": "s2"},
                {"from": "s2", "to": "s3"},
                {"from": "s3", "to": "s4"},
            ],
            "feedback": [{"from": "s4", "to": "s0", "label": "不达标"}],
        }

    monkeypatch.setattr("app.services.figures.parse.pipeline.call_llm_json", fake_llm)
    ctx = PipelineContext(
        description="",
        normalized_input="大模型微调流程图，包含数据准备、模型选择两个并行分支，汇合后进行训练，最后评估指标，若不达标则返回数据准备步骤",
        use_llm=True,
        model="test-model",
    )
    intent = DiagramIntent("workflow", "process_flow", diagram_type="flowchart")
    parsed = parse_pipeline(ctx, intent)
    assert called["n"] == 1
    assert parsed.source == "llm_pipeline"
    assert len(parsed.parsed_spec.get("nodes") or []) >= 5
