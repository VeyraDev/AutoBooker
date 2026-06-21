from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.services.figures.render.html_template import (
    compile_diagram_spec,
    render_infographic_spec,
    validate_and_normalize,
)


MVP_CASES = [
    (
        "rlhf_three_stage",
        "process_flow",
        "RLHF 训练流程包含 supervised fine-tuning、reward model training、PPO optimization 三个阶段",
        "horizontal_stage_cards",
    ),
    (
        "llm_training_8_steps",
        "process_flow",
        "完整 LLM 训练流程，步骤依次为：数据采集→数据清洗→预处理→预训练→监督微调→RLHF→评估→部署",
        "snake_cards",
    ),
    (
        "web_three_layers",
        "system_architecture",
        "Web应用三层架构图，顶层是前端React应用，中间层是FastAPI后端服务，底层是PostgreSQL数据库，各层之间用箭头标注HTTP请求和SQL查询",
        "vertical_layers",
    ),
    (
        "rag_three_column",
        "system_architecture",
        "RAG系统完整架构，左侧是文档预处理模块（解析、分块、嵌入），右侧是查询模块（向量检索、重排序、LLM生成），两侧共享向量数据库，箭头标明数据流向",
        "rag_three_column",
    ),
    (
        "lora_comparison",
        "comparison_matrix",
        "LoRA vs 全量微调对比，维度包括显存需求、训练速度、效果上限、适用场景",
        "comparison_matrix",
    ),
    (
        "decision_cards",
        "decision_tree",
        "决策树：最大化推理性能→选择 vLLM，构建复杂工作流→选择 LangChain，快速开发应用→选择 Hermes",
        "decision_cards",
    ),
    (
        "transformer_timeline",
        "timeline_roadmap",
        "Transformer 架构演进时间线：2017 Attention Is All You Need，2018 BERT，2020 GPT-3，2022 ChatGPT，2023 GPT-4，2024 多模态大模型普及",
        "horizontal_timeline",
    ),
    (
        "prompt_infographic",
        "infographic",
        "提示工程核心要点信息图，包含角色设定、思维链、输出格式、少样本学习、迭代优化",
        "grouped_infographic",
    ),
]


@pytest.mark.parametrize("case_id,subtype,prompt,expected_template", MVP_CASES)
def test_mvp_acceptance_prompts_compile_validate_and_render(
    case_id: str,
    subtype: str,
    prompt: str,
    expected_template: str,
    tmp_path: Path,
):
    spec, diagnostics = compile_diagram_spec(prompt, subtype=subtype, model="dummy", use_llm=False)
    validation = validate_and_normalize(spec, subtype=subtype)

    assert diagnostics["compiler_fallback"] is True
    assert validation["ok"], case_id
    assert validation["spec"].get("template_id")

    result = render_infographic_spec(validation["spec"], tmp_path / f"{case_id}.png", subtype=subtype)

    assert result.render_source == "infographic.template"
    assert result.optional_svg_path is None
    assert result.primary_png_path and result.primary_png_path.is_file()
    with Image.open(result.primary_png_path) as image:
        assert image.size[0] >= 1200
        assert image.size[1] >= 800


def test_mvp_fuzzy_input_requests_clarification():
    spec, diagnostics = compile_diagram_spec("高级图，好看一点", subtype="infographic", model="dummy", use_llm=False)

    assert diagnostics["compiler_fallback"] is True
    assert spec["needs_clarification"] is True
    assert spec["questions"]
