from pathlib import Path

from docx import Document
from PIL import Image

from app.services.figures.classification.resolver import build_classification_record
from app.services.figures.intent.resolve import resolve_intent_unified
from app.services.figures.intent.taxonomy import resolve_renderer_key
from app.services.figures.parse.architecture import parse_architecture
from app.services.figures.parse.comparison import parse_comparison
from app.services.figures.parse.decision_tree import _branches_to_graph
from app.services.figures.parse.hygiene import sanitize_diagram_spec
from app.services.figures.parse.infographic import parse_infographic
from app.services.figures.parse.mechanism import parse_mechanism
from app.services.figures.parse.network import parse_network
from app.services.figures.parse.pipeline import parse_pipeline
from app.services.figures.parse.registry import parse_diagram
import app.services.figures.parse.registry as parse_registry
from app.services.figures.parse.semantic_plan import _normalize_plan
from app.services.figures.parse.taxonomy import parse_taxonomy
from app.services.figures.parse.timeline import parse_timeline
from app.services.figures.parse.transformer import parse_transformer
from app.services.figures.pipeline.orchestrator import _resolve_intent
import app.services.figures.pipeline.orchestrator as orchestrator
from app.services.figures.render.structured.grammar import (
    generate_architecture_diagram,
    generate_comparison_diagram,
    generate_infographic_diagram,
    generate_network_diagram,
    generate_taxonomy_diagram,
    generate_timeline_diagram,
)
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.services.figure_render.figure_templates.structured_diagram import generate_structured_diagram
from app.services.tiptap_convert import _docx_figure_size


def test_process_flow_rules_build_short_title_and_edges():
    ctx = PipelineContext(
        description="",
        normalized_input="用户注册流程，步骤依次为：填写表单→邮件验证→完善资料→完成注册",
        use_llm=False,
    )
    intent = DiagramIntent("workflow", "process_flow", title="用户注册流程，从填写表单开始，经过邮件验证、完善资料，最终完成注册，共4个步骤，箭头连接")

    parsed = parse_pipeline(ctx, intent)
    spec = parsed.parsed_spec

    assert spec["layout"] == "TB"
    assert spec["title"] == "用户注册流程"
    assert len(spec["nodes"]) == 4
    assert len(spec["edges"]) == 3
    assert spec["edges"][0] == {"from": "s0", "to": "s1", "label": ""}


def test_rag_pipeline_is_not_routed_to_architecture_or_generic():
    text = "RAG pipeline：用户提问、向量化、检索知识库、生成回答，四个步骤，用箭头连接"
    ctx = PipelineContext(description="", normalized_input=text, use_llm=True)
    understanding = {
        "goal": "show_workflow",
        "confidence": 0.9,
        "candidate_diagrams": [{"type": "process_flow", "score": 0.92, "reason": "pipeline 步骤"}],
    }
    intent = resolve_intent_unified(ctx, understanding)

    assert intent.diagram_subtype == "process_flow"

    spec = parse_pipeline(PipelineContext(description="", normalized_input=text, use_llm=False), intent).parsed_spec

    assert [stage["label"] for stage in spec["stages"]] == ["用户提问", "向量化", "检索知识库", "生成回答"]
    assert len(spec["nodes"]) == 4
    assert len(spec["edges"]) == 3


def test_microservice_architecture_separates_modules_from_relations():
    text = "微服务架构图，包含API网关、用户服务、订单服务、支付服务、消息队列五个模块，API网关连接前三个服务，订单服务通过消息队列异步通知支付服务。"
    spec = parse_architecture(
        PipelineContext(description="", normalized_input=text, use_llm=False),
        DiagramIntent("architecture", "system_architecture", title="微服务架构图"),
    ).parsed_spec

    assert spec["layers"] == [
        {"label": "入口层", "modules": ["API网关"]},
        {"label": "服务层", "modules": ["用户服务", "订单服务", "支付服务"]},
        {"label": "基础设施层", "modules": ["消息队列"]},
    ]
    assert {node["label"] for node in spec["nodes"]} == {"API网关", "用户服务", "订单服务", "支付服务", "消息队列"}
    assert not any("连接" in node["label"] or "通过" in node["label"] for node in spec["nodes"])
    assert len(spec["edges"]) == 5
    assert any(edge["label"] == "异步" for edge in spec["edges"])


def test_finetune_flow_keeps_parallel_merge_and_feedback():
    text = "大模型微调流程图，包含数据准备、模型选择两个并行分支，汇合后进行训练，最后评估指标，若不达标则返回数据准备步骤"
    spec = parse_pipeline(
        PipelineContext(description="", normalized_input=text, use_llm=False),
        DiagramIntent("workflow", "process_flow", title="大模型微调流程"),
    ).parsed_spec

    assert [(node["label"], node["shape"], node["level"], node["column"]) for node in spec["nodes"]] == [
        ("数据准备", "box", 0, 0),
        ("模型选择", "box", 0, 1),
        ("训练", "rounded", 1, 0),
        ("评估指标", "rounded", 2, 0),
        ("是否达标", "diamond", 3, 0),
    ]
    assert {"from": "s4", "to": "s0", "label": "不达标"} in spec["edges"]
    assert spec["layout"] == "TB"


def test_registration_flow_does_not_turn_title_into_first_node():
    text = "用户注册流程，从填写表单开始，经过邮件验证、完善资料，最终完成注册，共4个步骤，箭头连接"
    spec = parse_pipeline(
        PipelineContext(description="", normalized_input=text, use_llm=False),
        DiagramIntent("workflow", "process_flow", title="用户注册流程"),
    ).parsed_spec

    assert [node["label"] for node in spec["nodes"]] == ["填写表单", "邮件验证", "完善资料", "完成注册"]
    assert len(spec["edges"]) == 3


def test_llm_candidate_overrides_stale_subtype_hint(monkeypatch):
    ctx = PipelineContext(
        description="",
        normalized_input="RAG pipeline：用户提问、向量化、检索知识库、生成回答，四个步骤",
        use_llm=True,
        model="dummy",
        subtype_hint="concept_diagram",
    )

    monkeypatch.setattr(
        orchestrator,
        "understand_intent",
        lambda _ctx, intent=None: {
            "goal": "show_workflow",
            "confidence": 0.9,
            "candidate_diagrams": [{"type": "process_flow", "score": 0.91, "reason": "pipeline"}],
        },
    )
    intent, _ = _resolve_intent(ctx)
    assert intent.diagram_subtype == "process_flow"


def test_llm_intent_is_primary_when_available(monkeypatch):
    ctx = PipelineContext(
        description="",
        normalized_input="RAG pipeline：用户提问、向量化、检索知识库、生成回答",
        use_llm=True,
        model="dummy",
    )

    monkeypatch.setattr(
        orchestrator,
        "understand_intent",
        lambda _ctx, intent=None: {
            "goal": "show_system_architecture",
            "confidence": 0.82,
            "candidate_diagrams": [{"type": "system_architecture", "score": 0.88, "reason": "RAG 架构"}],
        },
    )

    intent, _ = _resolve_intent(ctx)

    assert intent.diagram_subtype == "system_architecture"


def test_label_hygiene_removes_layout_instruction_text():
    spec, warnings, flags = sanitize_diagram_spec(
        {
            "nodes": [
                {"id": "n1", "label": "完整RAG pipeline->左侧用户提问", "shape": "rounded"},
                {"id": "n2", "label": "右侧生成回答，用箭头连接", "shape": "rounded"},
            ],
            "edges": [{"from": "n1", "to": "n2", "label": ""}],
        },
        subtype="process_flow",
    )

    assert [node["label"] for node in spec["nodes"]] == ["用户提问", "生成回答"]
    assert "label_hygiene" in flags
    assert warnings


def test_semantic_plan_normalizes_native_flow_fields_without_punctuation_rules():
    spec = _normalize_plan(
        {
            "title": "RAG 流程",
            "layout": "LR",
            "stages": [
                {"id": "ask", "label": "用户提问", "kind": "step"},
                {"id": "embed", "label": "向量化", "kind": "step"},
                {"id": "retrieve", "label": "检索知识库", "kind": "step"},
                {"id": "answer", "label": "生成回答", "kind": "output"},
            ],
            "edges": [
                {"from": "ask", "to": "embed", "label": ""},
                {"from": "embed", "to": "retrieve", "label": ""},
                {"from": "retrieve", "to": "answer", "label": ""},
            ],
        },
        DiagramIntent("workflow", "process_flow", title="RAG 流程"),
    )

    assert [node["label"] for node in spec["nodes"]] == ["用户提问", "向量化", "检索知识库", "生成回答"]
    assert len(spec["edges"]) == 3
    assert all(node.get("icon") for node in spec["nodes"])


def test_hygiene_flags_generic_center_node_regression_for_matrix():
    spec, warnings, flags = sanitize_diagram_spec(
        {
            "nodes": [
                {"id": "center", "label": "对比图"},
                {"id": "a", "label": "对象A"},
                {"id": "b", "label": "对象B"},
            ],
            "edges": [{"from": "center", "to": "a"}, {"from": "center", "to": "b"}],
        },
        subtype="comparison_matrix",
    )

    assert "generic_relation_regression" in flags
    assert warnings
    assert spec["diagram_subtype"] == "comparison_matrix"


def test_registry_fallback_uses_subtype_parser(monkeypatch):
    monkeypatch.setitem(
        parse_registry._PARSERS,
        "comparison_matrix",
        lambda _ctx, _intent: ParsedDiagram(
            {
                "title": "对比矩阵",
                "columns": ["对象A", "对象B"],
                "dimensions": ["速度", "成本"],
                "nodes": [{"id": "matrix", "label": "对比矩阵"}],
                "edges": [],
            },
            "fallback_comparison",
        ),
    )

    parsed = parse_registry.parse_diagram_fallback(
        PipelineContext(description="", normalized_input="对象A与对象B对比", use_llm=False),
        DiagramIntent("matrix", "comparison_matrix", title="对比矩阵"),
    )

    assert parsed.source == "fallback_comparison"
    assert parsed.parsed_spec["columns"] == ["对象A", "对象B"]


def test_registry_routes_subtypes_to_grammar_parsers():
    samples = [
        (DiagramIntent("workflow", "process_flow", title="流程"), "stages"),
        (DiagramIntent("knowledge", "mechanism_diagram", title="机制"), "steps"),
        (DiagramIntent("knowledge", "knowledge_graph", title="关系"), "concepts"),
        (DiagramIntent("knowledge", "infographic", title="信息图"), "blocks"),
        (DiagramIntent("architecture", "rag", title="RAG 架构"), "layers"),
    ]
    for intent, expected_key in samples:
        spec = parse_diagram(PipelineContext(description="", normalized_input="输入→处理→输出", use_llm=False), intent).parsed_spec
        assert expected_key in spec


def test_comparison_attention_and_infographic_do_not_fall_back_to_generic_relation():
    comparison = "对比图：DeepSpeed、vLLM、TGI三种推理框架，对比维度包括吞吐、延迟、显存、部署复杂度"
    c_intent = DiagramIntent("matrix", "comparison_matrix", 0.9, "test", "对比图")
    c_spec = parse_comparison(PipelineContext(description="", normalized_input=comparison, use_llm=False), c_intent).parsed_spec
    assert c_spec["columns"] == ["DeepSpeed", "vLLM", "TGI"]
    assert c_spec["dimensions"] == ["吞吐", "延迟", "显存", "部署复杂度"]
    assert "center" not in c_spec

    attention = "Attention 权重矩阵可视化，展示 Q/K score、mask 和 softmax 后的注意力权重"
    a_intent = DiagramIntent("matrix", "attention_matrix", 0.9, "test", "注意力矩阵")

    infographic = "信息图总结本章核心要点：角色设定、思维链、输出格式、少样本、迭代优化，五个信息块"
    i_intent = DiagramIntent("knowledge", "infographic", 0.9, "test", "信息图")
    i_spec = parse_infographic(PipelineContext(description="", normalized_input=infographic, use_llm=False), i_intent).parsed_spec
    assert [block["label"] for block in i_spec["blocks"]] == ["角色设定", "思维链", "输出格式", "少样本", "迭代优化"]
    assert "center" not in i_spec


def test_renderer_keys_route_subtypes_to_grammar_renderers():
    assert resolve_renderer_key("timeline_roadmap") == "structured.timeline"
    assert resolve_renderer_key("taxonomy_map") == "structured.taxonomy"
    assert resolve_renderer_key("comparison_matrix") == "structured.comparison"
    assert resolve_renderer_key("system_architecture") == "structured.architecture"
    assert resolve_renderer_key("knowledge_graph") == "structured.network"
    assert resolve_renderer_key("infographic") == "structured.infographic"
    assert resolve_renderer_key("rag") == "structured.architecture"
    assert resolve_renderer_key("transformer") == "structured.transformer"


def test_grammar_renderers_create_png_outputs(tmp_path: Path):
    cases = [
        (
            "timeline",
            generate_timeline_diagram,
            {"events": [{"time": "2017", "label": "Transformer"}, {"time": "2018", "label": "BERT"}]},
            "events=2",
        ),
        (
            "taxonomy",
            generate_taxonomy_diagram,
            {
                "root": "LLM",
                "children": [
                    {"label": "Open models", "children": [{"label": "LLaMA"}]},
                    {"label": "Closed models", "children": [{"label": "GPT-4"}]},
                ],
            },
            "groups=2",
        ),
        (
            "comparison",
            generate_comparison_diagram,
            {
                "columns": ["LoRA", "Full tuning"],
                "dimensions": ["Memory", "Speed"],
                "cells": [
                    {"dimension": "Memory", "values": {"LoRA": "Low", "Full tuning": "High"}},
                    {"dimension": "Speed", "values": {"LoRA": "Fast", "Full tuning": "Slow"}},
                ],
            },
            "columns=2",
        ),
        (
            "architecture",
            generate_architecture_diagram,
            {
                "layers": [
                    {"label": "Frontend", "modules": ["React"]},
                    {"label": "Service", "modules": ["FastAPI"]},
                    {"label": "Data", "modules": ["PostgreSQL"]},
                ],
                "connections": [
                    {"from": "React", "to": "FastAPI", "label": "HTTP"},
                    {"from": "FastAPI", "to": "PostgreSQL", "label": "SQL"},
                ],
            },
            "layers=3",
        ),
        (
            "network",
            generate_network_diagram,
            {
                "center": "LLM",
                "concepts": ["Pretrain", "Finetune", "RLHF"],
                "edges": [
                    {"from": "center", "to": "n0", "label": "base"},
                    {"from": "center", "to": "n1", "label": "adapt"},
                ],
            },
            "concepts=3",
        ),
        (
            "infographic",
            generate_infographic_diagram,
            {"blocks": [{"label": "Role", "items": ["Boundary"]}, {"label": "Format", "items": ["Schema"]}]},
            "blocks=2",
        ),
    ]

    for name, renderer, spec, summary_token in cases:
        summary, png = renderer(spec, tmp_path / f"{name}.png", title=name)

        assert summary_token in summary
        assert png.is_file()
        with Image.open(png) as img:
            width, height = img.size
        assert width >= 600
        assert height >= 300


def test_classification_record_adds_quality_diagnostics_for_missing_flow_edges():
    ctx = PipelineContext(
        description="",
        normalized_input="RAG pipeline：用户提问→向量化→检索→生成",
    )
    intent = DiagramIntent("workflow", "process_flow", title="RAG检索增强生成pipeline，步骤依次为用户提问到返回用户")
    parsed = ParsedDiagram(
        {
            "layout": "TB",
            "title": "RAG检索增强生成pipeline，步骤依次为用户提问到返回用户",
            "nodes": [
                {"id": "a", "label": "用户提问", "level": 0, "column": 0},
                {"id": "b", "label": "向量化", "level": 1, "column": 0},
                {"id": "c", "label": "检索", "level": 2, "column": 0},
            ],
            "edges": [],
        }
    )

    record = build_classification_record(ctx, intent, parsed).to_json()

    assert record["prompt_spec"]["title"] == "RAG检索增强生成pipeline"
    assert "edge_gap" in record["quality_flags"]
    assert record["layout_strategy"] == "TB"


def test_low_text_structured_visual_can_route_to_image_api():
    ctx = PipelineContext(description="", normalized_input="低文字流程视觉图：提问到回答")
    intent = DiagramIntent("workflow", "process_flow", title="问答流程")
    parsed = ParsedDiagram(
        {
            "render_mode": "image_api",
            "structure_summary": "低文字流程视觉化",
            "nodes": [
                {"id": "a", "label": "提问", "level": 0, "column": 0},
                {"id": "b", "label": "检索", "level": 1, "column": 0},
                {"id": "c", "label": "回答", "level": 2, "column": 0},
            ],
            "edges": [{"from": "a", "to": "b", "label": ""}, {"from": "b", "to": "c", "label": ""}],
        }
    )

    record = build_classification_record(ctx, intent, parsed).to_json()

    assert record["renderer"] == "illustration.image_api"
    assert "image_api_structured_visual" in record["quality_flags"]
    assert record["prompt_spec"]["visual_description"] == "低文字流程视觉化"


def test_decision_tree_tags_do_not_split_latin_words():
    spec = _branches_to_graph(
        {
            "root": "你的主要需求是什么？",
            "branches": [
                {
                    "label": "构建复杂工作流",
                    "target": "LangChain",
                    "tags": ["灵活的链式调用与Agent编排", "支持多模型、工具和记忆"],
                }
            ],
        }
    )

    labels = [node["label"] for node in spec["nodes"]]

    assert "选择 LangChain" in labels
    assert not any(label in {"Ag", "Pa", "Agent编…"} for label in labels)
    assert any("Agent" in label for label in labels)


def test_structured_diagram_renders_without_raw_long_title(tmp_path: Path):
    out = tmp_path / "flow.png"
    spec = {
        "diagram_subtype": "process_flow",
        "layout": "TB",
        "title": "用户注册流程，从填写表单开始，经过邮件验证、完善资料，最终完成注册，共4个步骤，箭头连接",
        "nodes": [
            {"id": "a", "label": "填写表单", "level": 0, "column": 0},
            {"id": "b", "label": "邮件验证", "level": 1, "column": 0},
            {"id": "c", "label": "完善资料", "level": 2, "column": 0},
            {"id": "d", "label": "完成注册", "level": 3, "column": 0},
        ],
        "edges": [],
    }

    summary, png = generate_structured_diagram(spec, out)

    assert "nodes=4" in summary
    assert png.is_file()
    assert png.with_suffix(".svg").is_file()
    assert png.with_suffix(".svg").read_text(encoding="utf-8").lstrip().startswith("<svg")
    with Image.open(png) as img:
        width, height = img.size
    assert width > height
    assert width <= 2600


def test_docx_figure_size_caps_square_and_tall_images(tmp_path: Path):
    square = tmp_path / "square.png"
    tall = tmp_path / "tall.png"
    Image.new("RGB", (1024, 1024), "white").save(square)
    Image.new("RGB", (900, 2400), "white").save(tall)

    square_w, square_h = _docx_figure_size(square)
    tall_w, tall_h = _docx_figure_size(tall)

    assert round(square_w, 1) == 4.2
    assert round(square_h or 0, 1) == 4.2
    assert tall_h == 5.8
    assert tall_w < 5.5


def test_timeline_parser_outputs_events_not_plain_generic_nodes():
    ctx = PipelineContext(
        description="",
        normalized_input="Transformer架构演进时间线，2017年Attention Is All You Need，2018年BERT，2020年GPT-3，2022年ChatGPT",
        use_llm=False,
    )
    intent = DiagramIntent("timeline", "timeline_roadmap", title="Transformer架构演进时间线")

    spec = parse_timeline(ctx, intent).parsed_spec

    assert [event["time"] for event in spec["events"]] == ["2017", "2018", "2020", "2022"]
    assert spec["layout"] == "LR"
    assert len(spec["edges"]) == len(spec["events"]) - 1


def test_taxonomy_parser_outputs_root_children_tree():
    ctx = PipelineContext(
        description="",
        normalized_input='大语言模型分类图，根节点为"大语言模型"，分为开源模型和闭源模型两类，开源模型下有LLaMA、Mistral、Qwen，闭源模型下有GPT-4、Claude、Gemini',
        use_llm=False,
    )
    intent = DiagramIntent("knowledge", "taxonomy_map", title="大语言模型分类图")

    spec = parse_taxonomy(ctx, intent).parsed_spec

    assert spec["root"] == "大语言模型"
    assert {child["label"] for child in spec["children"]} >= {"开源模型", "闭源模型"}
    assert any(grand["label"] == "LLaMA" for child in spec["children"] for grand in child["children"])
    assert len(spec["edges"]) >= 2


def test_comparison_parser_outputs_columns_and_dimensions():
    ctx = PipelineContext(
        description="",
        normalized_input="LoRA与全量微调对比图，对比维度包括显存需求、训练速度、效果上限、适用场景四个维度",
        use_llm=False,
    )
    intent = DiagramIntent("matrix", "comparison_matrix", title="LoRA与全量微调对比图")

    spec = parse_comparison(ctx, intent).parsed_spec

    assert spec["columns"] == ["LoRA", "全量微调"]
    assert spec["dimensions"][:2] == ["显存需求", "训练速度"]
    assert spec["diagram_subtype"] == "comparison_matrix"


def test_architecture_parser_outputs_layers_and_connections_graph():
    ctx = PipelineContext(
        description="",
        normalized_input="Web应用三层架构图，顶层是前端React应用，中间层是FastAPI后端服务，底层是PostgreSQL数据库，各层之间用箭头标注HTTP请求和SQL查询",
        use_llm=False,
    )
    intent = DiagramIntent("architecture", "system_architecture", title="Web应用三层架构图")

    spec = parse_architecture(ctx, intent).parsed_spec

    assert [layer["label"] for layer in spec["layers"]] == ["前端层", "服务层", "数据层"]
    assert any("React" in module for module in spec["layers"][0]["modules"])
    assert len(spec["edges"]) >= 2


def test_transformer_parser_outputs_ordered_encoder_decoder_layers():
    ctx = PipelineContext(
        description="",
        normalized_input="标准Transformer编码器-解码器架构图，左侧编码器包含多头自注意力和前馈网络，N次堆叠，右侧解码器包含掩码自注意力、交叉注意力和前馈网络，N次堆叠",
        use_llm=False,
    )
    intent = DiagramIntent("knowledge", "transformer", title="标准Transformer编码器-解码器架构图")

    spec = parse_transformer(ctx, intent).parsed_spec

    assert spec["encoder"]["layers"] == ["multi_head_self_attention", "add_norm", "feed_forward", "add_norm"]
    assert spec["decoder"]["layers"][:3] == ["masked_multi_head_self_attention", "add_norm", "cross_attention"]
    assert spec["connections"][0]["type"] == "cross_attention"


def test_legacy_transformer_parser_is_grammar_shim():
    ctx = PipelineContext(description="", normalized_input="Transformer 编码器解码器架构", use_llm=False)
    intent = DiagramIntent("knowledge", "transformer", title="Transformer 架构")

    spec = parse_transformer(ctx, intent).parsed_spec
    assert spec.get("encoder", {}).get("layers")
    assert spec["diagram_subtype"] == "transformer"


def test_network_parser_outputs_relationship_graph_not_taxonomy_tree():
    ctx = PipelineContext(
        description="",
        normalized_input='LLM与相关概念的关系图，LLM中心，连接预训练、微调、RLHF、推理、评估五个节点，每条连线标注关系类型如"影响"',
        use_llm=False,
    )
    intent = DiagramIntent("knowledge", "knowledge_graph", title="LLM关系图")

    spec = parse_network(ctx, intent).parsed_spec

    assert spec["center"] == "LLM"
    assert "concepts" in spec
    assert "children" not in spec


def test_infographic_parser_outputs_blocks():
    ctx = PipelineContext(
        description="",
        normalized_input='信息图总结本章"提示工程"核心要点，包含5个关键概念的图标化展示：角色设定、思维链、输出格式、少样本、迭代优化',
        use_llm=False,
    )
    intent = DiagramIntent("knowledge", "infographic", title="提示工程核心要点")

    spec = parse_infographic(ctx, intent).parsed_spec

    assert [block["label"] for block in spec["blocks"][:2]] == ["角色设定", "思维链"]
