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


class RoutedRewriteClient:
    def __init__(self, rewritten: str, *, safety: dict | None = None) -> None:
        self.rewritten = rewritten
        self.safety = safety or {"safe": True, "semantic_change": False, "reason": "通过"}
        self.calls: list[list[dict[str, str]]] = []

    def chat_completion(self, messages, **_kwargs) -> str:
        import json

        self.calls.append(messages)
        system = messages[0]["content"]
        if "事实抽取器" in system:
            return '{"facts": []}'
        if "局部改写安全校验器" in system:
            return json.dumps(self.safety, ensure_ascii=False)
        return self.rewritten


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


def test_dedupe_uses_on_demand_rewrite_prompt_and_one_style_patch(monkeypatch):
    monkeypatch.setattr("app.services.dedupe_service.get_ai_detect_provider", lambda: FakeDetector())
    original = "模板化表达需要通过更具体的论证来压实。"
    rewritten = "这段论证需要补出具体条件，才能形成有效判断。"
    client = RoutedRewriteClient(rewritten)

    result = DedupeService().dedupe_text(
        original,
        client=client,
        chat_model="fake",
        style_profile="biography",
        finding_instruction="删除空泛总结，保留人物叙事语气",
    )

    rewrite_system = next(call[0]["content"] for call in client.calls if "局部改写器" in call[0]["content"])
    assert result.text == rewritten
    assert "人物传记补丁" in rewrite_system
    assert "学术专著补丁" not in rewrite_system
    assert "删除空泛总结" in next(call[1]["content"] for call in client.calls if "局部改写器" in call[0]["content"])


def test_dedupe_calls_safety_prompt_only_for_ambiguous_semantic_change(monkeypatch):
    monkeypatch.setattr("app.services.dedupe_service.get_ai_detect_provider", lambda: FakeDetector())
    original = "模板化表达需要说明原有约束与适用范围。"
    client = RoutedRewriteClient(
        "结论完全改变。",
        safety={"safe": False, "semantic_change": True, "reason": "论证边界丢失"},
    )

    result = DedupeService().dedupe_text(original, client=client, chat_model="fake")

    assert any("局部改写安全校验器" in call[0]["content"] for call in client.calls)
    assert result.text == original
    assert result.report["status"] == "failed"
    assert result.report["llm_safety"]["safe"] is False


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
