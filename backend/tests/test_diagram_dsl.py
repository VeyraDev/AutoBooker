from app.services.figures.dsl import build_dsl_from_parsed, default_dsl_for_type, dsl_to_parsed_spec
from app.services.figures.parse.architecture import parse_architecture
from app.services.figures.parse.extractor import _thin_sanitize, extract_semantics
from app.services.figures.parse.pipeline import parse_pipeline
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.services.figures.validate.dsl_validator import validate_and_repair


def test_default_flowchart_not_empty():
    dsl = default_dsl_for_type("flowchart", title="流程图")
    assert len(dsl.nodes) >= 3
    assert len(dsl.edges) >= 2
    assert dsl.layout["direction"] == "TB"


def test_build_dsl_from_architecture_layers():
    text = "微服务架构图，包含API网关、用户服务、订单服务、支付服务、消息队列五个模块，API网关连接前三个服务。"
    parsed = parse_architecture(
        PipelineContext(description="", normalized_input=text, use_llm=False),
        DiagramIntent("architecture", "system_architecture", diagram_type="architecture"),
    )
    dsl = build_dsl_from_parsed(
        DiagramIntent("architecture", "system_architecture", diagram_type="architecture"),
        parsed,
    )
    labels = [n.label for n in dsl.nodes]
    assert "API网关" in labels
    assert "用户服务" in labels
    assert not any("连接前三个" in lb for lb in labels)
    assert len(dsl.edges) >= 3


def test_extract_semantics_registration_flow_tb():
    ctx = PipelineContext(
        description="",
        normalized_input="用户注册流程，步骤依次为：填写表单→邮件验证→完善资料→完成注册",
        use_llm=False,
    )
    intent = DiagramIntent("workflow", "process_flow", diagram_type="flowchart", title="用户注册流程")
    dsl = extract_semantics(ctx, intent)
    assert dsl.diagram_type == "flowchart"
    assert len(dsl.nodes) == 4
    assert dsl.layout.get("direction") == "TB" or dsl_to_parsed_spec(dsl).get("layout") == "TB"


def test_thin_sanitize_dedupes_edges():
    from app.services.figures.schemas.dsl import DiagramDSL, DiagramEdge, DiagramNode

    dsl = DiagramDSL(
        diagram_type="flowchart",
        title="流程",
        nodes=[
            DiagramNode(id="a", label="步骤A", type="process"),
            DiagramNode(id="b", label="步骤B", type="process"),
        ],
        edges=[
            DiagramEdge(source="a", target="b", label=""),
            DiagramEdge(source="a", target="b", label=""),
        ],
    )
    cleaned = _thin_sanitize(dsl)
    assert len(cleaned.edges) == 1


def test_validate_and_repair_empty_dsl():
    from app.services.figures.schemas.dsl import DiagramDSL

    dsl = DiagramDSL(diagram_type="flowchart", title="空图", nodes=[], edges=[])
    repaired, result = validate_and_repair(dsl)
    assert result.repaired
    assert len(repaired.nodes) >= 3


def test_decision_flow_dsl_from_pipeline():
    text = "大模型微调流程：训练→评估指标→是否达标，达标则结束，不达标则继续训练"
    ctx = PipelineContext(description="", normalized_input=text, use_llm=False)
    intent = DiagramIntent("decision", "decision_tree", diagram_type="decision_flow")
    parsed = parse_pipeline(ctx, intent)
    dsl = build_dsl_from_parsed(intent, parsed, diagram_type="decision_flow")
    labels = [n.label for n in dsl.nodes]
    assert any("训练" in lb or "评估" in lb for lb in labels)
