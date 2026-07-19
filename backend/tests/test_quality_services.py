from pathlib import Path
from types import SimpleNamespace

from app.services.ai_detect.provider import AiDetectResult
from app.services.dedupe_service import DedupeService
from app.services.figure_lint import lint_figures
from app.services.figures.layout.linear import layout_linear
from app.services.figures.graph.schema import GraphIR, GraphNode
from app.services.figures.render.result import coerce_render_result


class FakeClient:
    def __init__(self, output: str) -> None:
        self.output = output

    def chat_completion(self, *_args, **_kwargs) -> str:
        return self.output


class FakeDetector:
    def detect(self, text: str) -> AiDetectResult:
        score = 80.0 if "模板化" in text else 25.0
        return AiDetectResult(overall_score=score, provider="fake", segments=[], body_hash="hash")


def test_dedupe_service_preserves_protected_tokens_and_reports_risk_drop(monkeypatch):
    monkeypatch.setattr("app.services.dedupe_service.get_ai_detect_provider", lambda: FakeDetector())
    original = "模板化表达：2024年，系统在图1-1中达到87%，参考文献[3]说明了API Gateway。"
    rewritten = "2024年，系统在图1-1中达到87%，参考文献[3]说明了API Gateway，表达更加自然。"

    result = DedupeService().dedupe_text(
        original,
        client=FakeClient(rewritten),
        chat_model="fake",
    )

    assert result.text == rewritten
    assert result.report["before_ai_risk"] == 80.0
    assert result.report["after_ai_risk"] == 25.0
    assert result.report["protected_tokens_changed"] == []
    assert result.report["meaning_preserved"] is True


def test_dedupe_service_fails_when_protected_tokens_change(monkeypatch):
    monkeypatch.setattr("app.services.dedupe_service.get_ai_detect_provider", lambda: FakeDetector())
    original = "2024年收入为87%，见[3]。"
    rewritten = "收入表现较好。"

    result = DedupeService().dedupe_text(
        original,
        client=FakeClient(rewritten),
        chat_model="fake",
    )

    assert result.report["status"] == "failed"
    assert result.report["protected_tokens_changed"]


def test_figure_lint_surfaces_generation_quality_report():
    fig = SimpleNamespace(
        figure_number="1-1",
        caption="source: generated",
        raw_annotation="",
        file_path="",
        file_url="/static/figures/x.png",
        classification_json={
            "quality_report": {
                "status": "warning",
                "semantic_score": 0.8,
                "layout_score": 0.6,
                "render_score": 1.0,
                "failures": [],
                "warnings": ["label_overflow_risk"],
                "recommendations": ["shorten labels"],
            }
        },
    )

    result = lint_figures("见图1-1。", [fig])

    issue = next(i for i in result["issues"] if i["issue_type"] == "figure_quality_report")
    assert issue["quality_evidence"]["warnings"] == ["label_overflow_risk"]


def test_render_result_contract_maps_svg_renderer_to_primary_png(tmp_path: Path):
    svg = tmp_path / "figure.svg"
    png = tmp_path / "figure.png"
    svg.write_text("<svg></svg>", encoding="utf-8")
    png.write_bytes(b"png")

    result = coerce_render_result("image/svg+xml", svg, png)

    assert result.primary_png_path == png
    assert result.optional_svg_path == svg
    assert result.diagnostics["primary_png_present"] is True


def test_linear_layout_uses_dynamic_node_width():
    graph = GraphIR(
        diagram_type="flow",
        title="",
        nodes=[
            GraphNode(id="a", label="短"),
            GraphNode(id="b", label="这是一个很长的中文节点标签用于测试宽度"),
        ],
    )

    layout = layout_linear(graph)

    assert layout.node_positions["b"].width > layout.node_positions["a"].width
