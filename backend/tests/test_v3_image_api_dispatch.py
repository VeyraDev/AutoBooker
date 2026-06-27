from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.book import Book, BookType
from app.models.figure import Figure, FigureType
from app.services.figures.render.image_api.canvas import openai_size_for_canvas, wanx_size_for_canvas
from app.services.figures.render.image_api.pipeline import build_figure_prompt
from app.services.figures.render.image_api.layoutscript import generate_layout_script, parse_classifier_agent_output
from app.services.figures.render.image_api.prompt_constraints import build_layout_agent_prompt
from app.services.figures.generation import sync_figure_urls_from_disk
from app.services.figures.intent.taxonomy import (
    RENDERER_ILLUSTRATION,
    RENDERER_UPLOAD,
)
from app.services.figures.pipeline.orchestrator import classify_figure_description
from app.services.figures.render.dispatcher import render_figure


def _understanding(candidate_type: str, *, score: float = 0.93, route: str = "image_api") -> dict:
    return {
        "route": route,
        "confidence": score,
        "goal": "show_workflow",
        "diagram_candidates": [{"type": candidate_type, "score": score, "reason": "test"}],
    }


def test_classifier_agent_output_parses_to_internal_dict():
    text = """主图类：system_architecture
辅图类：process_flow
不要画成：线性流程图
分类理由：用户描述的是模块与共享向量数据库
布局规划器应重点处理的风险：不要漏掉共享组件"""

    parsed = parse_classifier_agent_output(text)

    assert parsed
    assert parsed["primary_type"] == "system_architecture"
    assert parsed["secondary_type"] == "process_flow"
    assert parsed["do_not_draw_as"] == "线性流程图"
    assert parsed["layout_risks"] == "不要漏掉共享组件"
    assert parsed["diagram_candidates"][0]["type"] == "system_architecture"


def test_layout_agent_prompt_loads_only_current_type_constraints():
    prompt = build_layout_agent_prompt(
        "微服务架构图，包含 API 网关、用户服务、订单服务、消息队列",
        "system_architecture",
    )

    assert "当前主图类布局约束" in prompt
    assert "重点表现系统由哪些层、模块、服务" in prompt
    assert "根据内容选择上下分层、左右分区、中心共享组件、服务拓扑或双通道结构" in prompt
    assert "每个主要步骤画成清晰步骤节点" not in prompt
    assert "时间轴必须是一级主结构" not in prompt


def test_layout_agent_prompt_includes_process_flow_canvas_guidance():
    prompt = build_layout_agent_prompt(
        "用户注册流程，从填写表单开始，经过邮件验证、完善资料，最终完成注册，共4个步骤，箭头连接",
        "process_flow",
    )

    assert "【画布比例与安全边距】" in prompt
    assert "横向宽画布" in prompt
    assert "安全边距" in prompt
    assert "蛇形折返" in prompt


def test_layout_agent_fallback_keeps_canvas_section():
    layout_script, used_fallback = generate_layout_script(
        "用户注册流程，从填写表单开始，经过邮件验证、完善资料，最终完成注册，共4个步骤，箭头连接",
        "process_flow",
        model="dummy",
        use_llm=True,
    )

    assert used_fallback is True
    assert "【画布比例与安全边距】" in layout_script
    assert "横向宽画布" in layout_script
    assert "安全边距" in layout_script


def test_process_flow_canvas_selects_wide_image_sizes():
    assert openai_size_for_canvas("gpt-image-1", subtype="process_flow", configured_size="1024x1024") == "1536x1024"
    assert openai_size_for_canvas("dall-e-3", subtype="process_flow", configured_size="1024x1024") == "1792x1024"
    assert openai_size_for_canvas("dall-e-2", subtype="process_flow", configured_size="1024x1024") == "1024x1024"
    assert openai_size_for_canvas("gpt-image-1", subtype="process_flow", configured_size="1024x1536") == "1024x1536"
    assert wanx_size_for_canvas(subtype="process_flow") == "1280*720"


def test_infographic_canvas_selects_wide_image_sizes_for_summary_cards():
    assert openai_size_for_canvas("gpt-image-2", subtype="infographic", configured_size="1024x1024") == "1536x1024"
    assert wanx_size_for_canvas(subtype="infographic") == "1280*720"


def test_layout_agent_prompt_guards_against_empty_architecture_and_unlabeled_branches():
    architecture_prompt = build_layout_agent_prompt(
        "RAG系统完整架构，左侧是文档预处理模块（解析、分块、嵌入），右侧是查询模块（向量检索、重排序、LLM生成），两侧共享向量数据库，箭头标明数据流向",
        "system_architecture",
    )
    flow_prompt = build_layout_agent_prompt(
        "大模型微调流程图，包含数据准备、模型选择两个并行分支，汇合后进行训练，最后评估指标，若不达标则返回数据准备步骤",
        "process_flow",
    )

    assert "不得生成只有边框、底色或空白卡片的空区域" in architecture_prompt
    assert "左右/上下分区中的模块必须逐项落位" in architecture_prompt
    assert "内容完整性核对" in architecture_prompt
    assert "无标签普通箭头" in flow_prompt
    assert "箭头 / 关系标签" in flow_prompt


def test_comparison_and_infographic_prompts_require_cell_fill_and_summary_structure():
    comparison_prompt = build_layout_agent_prompt(
        "LoRA与全量微调对比图，比较显存需求、训练速度、效果上限、适用场景，并用颜色深浅区分效果强弱",
        "comparison_matrix",
    )
    infographic_prompt = build_layout_agent_prompt(
        "章节总结图：提示工程包含角色设定、思维链、输出格式、少样本、迭代优化",
        "infographic",
    )

    assert "矩阵单元格不得留空" in comparison_prompt
    assert "浅到深的低饱和色阶" in comparison_prompt
    assert "不得只画几个图标圆点" in infographic_prompt
    assert "卡片网格" in infographic_prompt


def test_layout_prompt_uses_generic_chinese_constraints():
    prompt = build_layout_agent_prompt(
        "甲系统包含甲模块、乙模块和共享组件，甲模块通过共享组件连接乙模块",
        "system_architecture",
    )

    assert "布局脚本" in prompt
    for forbidden in ("RAG", "Transformer", "LayoutScript", "Layout Agent", "Q/K/V", "Softmax"):
        assert forbidden not in prompt


def test_image_prompt_uses_layoutscript_not_raw_user_input():
    raw_user_input = "RAW_ONLY_用户原始输入不应进入ImagePrompt"
    layout_script = """【图类确认】
主图类：process_flow
辅图类：无
这张图首先应该被读作：流程图
不要画成：系统架构图

【可见文字白名单】
标题：
- 用户注册流程
节点 / 模块文字：
- 填写表单
- 邮件验证
- 完成注册
箭头 / 关系标签：
- 无

【整体版式】
横向三步流程。"""

    prompt = build_figure_prompt(
        raw_user_input,
        "",
        sub_kind="process_flow",
        layout_script=layout_script,
        prompt_mode="full_v3",
    )

    assert prompt.startswith("请根据下面的布局脚本生成图片。")
    assert "布局脚本是唯一结构依据。" in prompt
    assert "用户注册流程" in prompt
    assert raw_user_input not in prompt
    assert "不得新增任何不在白名单中的可见文字" in prompt
    assert "画成清晰步骤流程图" in prompt
    assert "不得生成空壳图" in prompt
    assert "无标签分支线" in prompt
    assert '"nodes"' not in prompt
    assert '"edges"' not in prompt


def test_direct_prompt_fallback_still_available_without_layoutscript():
    raw_user_input = "用户注册流程：填写表单 -> 邮件验证 -> 完成注册"

    prompt = build_figure_prompt(raw_user_input, "", sub_kind="process_flow")

    assert prompt.startswith(raw_user_input)
    assert "不要调用布局规划器" in prompt
    assert "每个主要步骤画成清晰步骤节点" in prompt
    assert "不得翻译、改写、扩写或替换" in prompt


def test_llm_candidate_overrides_stale_subtype_hint(monkeypatch):
    monkeypatch.setattr(
        "app.services.figures.intent.understand._call_intent_understanding_llm",
        lambda _ctx: _understanding("process_flow"),
    )

    record = classify_figure_description(
        "A 到 B 的流程",
        model="dummy",
        use_llm=True,
        subtype_hint="concept_diagram",
    )

    assert record["diagram_subtype"] == "process_flow"
    assert record["subtype"] == "process_flow"
    assert record["renderer"] == RENDERER_ILLUSTRATION
    assert record["parsed_spec"]["render_mode"] == "image_api"
    assert record["parsed_spec"]["prompt_mode"] == "no_layout"
    assert record["parsed_spec"]["image_input"]
    assert "layout_agent" not in [t["step"] for t in record["pipeline_trace"]]
    assert "visual_brief" not in [t["step"] for t in record["pipeline_trace"]]


def test_default_prompt_spec_has_no_domain_template_terms():
    record = classify_figure_description(
        "甲系统包含甲模块和乙模块，甲模块连接乙模块",
        model="dummy",
        use_llm=False,
        subtype_hint="system_architecture",
    )

    assert record["renderer"] == RENDERER_ILLUSTRATION
    assert record["parsed_spec"]["render_mode"] == "image_api"
    prompt_spec_text = str(record["prompt_spec"])
    for forbidden in ("RAG", "Transformer", "LayoutScript", "Layout Agent", "Q/K/V", "Softmax"):
        assert forbidden not in prompt_spec_text


def test_llm_classifies_all_v3_image_api_subtypes(monkeypatch):
    current = {"subtype": "process_flow"}

    monkeypatch.setattr(
        "app.services.figures.intent.understand._call_intent_understanding_llm",
        lambda _ctx: _understanding(current["subtype"]),
    )

    for subtype in [
        "process_flow",
        "system_architecture",
        "mechanism_diagram",
        "comparison_matrix",
        "concept_diagram",
        "infographic",
        "taxonomy_map",
        "decision_tree",
        "timeline_roadmap",
    ]:
        current["subtype"] = subtype
        record = classify_figure_description(
            f"test prompt for {subtype}",
            model="dummy",
            use_llm=True,
            subtype_hint="rag",
        )

        assert record["diagram_subtype"] == subtype
        assert record["subtype"] == subtype
        assert record["renderer"] == RENDERER_ILLUSTRATION
        assert record["parsed_spec"]["render_mode"] == "image_api"
        assert record["parsed_spec"]["prompt_mode"] == "no_layout"
        assert record["parsed_spec"]["image_input"]


def test_scene_illustration_remains_image_api(monkeypatch):
    monkeypatch.setattr(
        "app.services.figures.intent.understand._call_intent_understanding_llm",
        lambda _ctx: _understanding("scene_illustration"),
    )

    record = classify_figure_description("AI 助手帮助用户写作的场景插图", model="dummy", use_llm=True)

    assert record["diagram_subtype"] == "scene_illustration"
    assert record["renderer"] == RENDERER_ILLUSTRATION
    assert record["parsed_spec"]["render_mode"] == "image_api"
    assert record["parsed_spec"]["image_input"]


def test_chart_uses_image_api_no_layout(monkeypatch):
    chart_calls: list[str] = []
    monkeypatch.setattr(
        "app.services.figures.intent.understand._call_intent_understanding_llm",
        lambda _ctx: _understanding("chart", route="chart"),
    )
    monkeypatch.setattr(
        "app.services.figures.pipeline.orchestrator.generate_data_chart_script",
        lambda *args, **kwargs: chart_calls.append("called") or ("2024 年 A=10，B=20 柱状图脚本", False),
    )

    record = classify_figure_description(
        "2024 年 A=10，B=20，生成柱状图",
        model="dummy",
        use_llm=True,
    )

    assert record["diagram_subtype"] == "chart"
    assert record["renderer"] == RENDERER_ILLUSTRATION
    assert record["parsed_spec"]["render_mode"] == "image_api"
    assert record["parsed_spec"]["prompt_mode"] == "no_layout"
    assert chart_calls == ["called"]


def test_screenshot_is_upload_only(monkeypatch):
    monkeypatch.setattr(
        "app.services.figures.intent.understand._call_intent_understanding_llm",
        lambda _ctx: _understanding("screenshot", route="screenshot_placeholder"),
    )

    record = classify_figure_description("这里需要产品界面截图", model="dummy", use_llm=True)

    assert record["diagram_subtype"] == "screenshot"
    assert record["renderer"] == RENDERER_UPLOAD
    assert "screenshot_placeholder" in record["quality_flags"]


def test_old_aliases_do_not_become_final_subtypes():
    for alias in ["rag", "agent", "transformer", "attention_matrix", "swot", "knowledge_graph", "org_chart"]:
        record = classify_figure_description(
            f"test prompt for old alias {alias}",
            model="dummy",
            use_llm=False,
            subtype_hint=alias,
        )

        assert record["diagram_subtype"] == "concept_diagram"
        assert record["subtype"] == "concept_diagram"
        assert record["renderer"] == RENDERER_ILLUSTRATION


def test_render_figure_image_api_uses_no_layout_input(monkeypatch, tmp_path: Path):
    calls: list[tuple[str, str, str | None, str | None]] = []

    def fake_generate(
        description: str,
        output_path: Path,
        *,
        style_type: str = "",
        sub_kind: str = "figure",
        layout_script: str | None = None,
        prompt_mode: str | None = None,
    ):
        calls.append((description, sub_kind, layout_script, prompt_mode))
        output_path.write_bytes(b"png")
        return "prompt", output_path

    monkeypatch.setattr(
        "app.services.figures.render.dispatcher.generate_figure_image",
        fake_generate,
    )
    book = Book(id=uuid4(), title="Book", book_type=BookType.nonfiction, style_type="")
    fig = Figure(
        id=uuid4(),
        book_id=book.id,
        chapter_index=1,
        figure_type=FigureType.figure,
        raw_annotation="RAG 系统架构：用户、检索器、向量库、LLM",
        renderer=RENDERER_ILLUSTRATION,
        subtype="system_architecture",
        classification_json={
            "diagram_subtype": "system_architecture",
            "normalized_input": "SHOULD_NOT_USE",
            "parsed_spec": {
                "image_input": "RAG 系统架构：用户、检索器、向量库、LLM",
                "prompt_mode": "no_layout",
            },
        },
    )

    result = render_figure(fig, book, tmp_path / "figure.png")

    assert result.primary_png_path and result.primary_png_path.is_file()
    assert calls == [
        (
            "RAG 系统架构：用户、检索器、向量库、LLM",
            "system_architecture",
            None,
            "no_layout",
        )
    ]


def test_render_figure_old_compositor_record_is_forced_to_image_api(monkeypatch, tmp_path: Path):
    calls: list[tuple[str, str, str | None]] = []

    def fake_image_api(
        description: str,
        output_path: Path,
        *,
        style_type: str = "",
        sub_kind: str = "figure",
        layout_script: str | None = None,
        prompt_mode: str | None = None,
    ):
        calls.append((description, sub_kind, layout_script))
        output_path.write_bytes(b"png")
        return "prompt", output_path

    monkeypatch.setattr(
        "app.services.figures.render.dispatcher.generate_figure_image",
        fake_image_api,
    )
    book = Book(id=uuid4(), title="Book", book_type=BookType.nonfiction, style_type="")
    fig = Figure(
        id=uuid4(),
        book_id=book.id,
        chapter_index=1,
        figure_type=FigureType.figure,
        raw_annotation="用户注册流程",
            renderer="generic.compositor",
        subtype="process_flow",
        classification_json={
            "diagram_subtype": "process_flow",
            "parsed_spec": {
                "render_mode": "generic_compositor",
                "diagram_spec": {
                    "chart_type": "process_flow",
                    "template_id": "horizontal_stage_cards",
                    "title": "用户注册流程",
                    "stages": [
                        {"title": "填写表单", "bullets": ["输入账号信息"]},
                        {"title": "邮件验证", "bullets": ["确认邮箱地址"]},
                        {"title": "完善资料", "bullets": ["补充个人信息"]},
                        {"title": "完成注册", "bullets": ["进入可用状态"]},
                    ],
                },
            },
        },
    )

    result = render_figure(fig, book, tmp_path / "figure.png")

    assert result.render_source == "prompt"
    assert result.primary_png_path and result.primary_png_path.is_file()
    assert result.optional_svg_path is None
    assert calls == [("用户注册流程", "process_flow", None)]


def test_sync_png_sets_file_url_and_clears_svg(monkeypatch, tmp_path: Path):
    from app.services.figures.storage import manager as storage_manager

    class _Settings:
        @property
        def figures_path(self):
            return tmp_path

    monkeypatch.setattr(storage_manager, "settings", _Settings())
    book_id = uuid4()
    figure_id = uuid4()
    png = storage_manager.figure_storage.png_path(book_id, 1, figure_id)
    png.write_bytes(b"png")
    fig = SimpleNamespace(book_id=book_id, chapter_index=1, id=figure_id, svg_url="old.svg")

    sync_figure_urls_from_disk(fig)

    assert fig.file_path == str(png.resolve())
    assert fig.file_url == f"/static/figures/{book_id}/1/{figure_id}/figure.png"
    assert fig.svg_url is None


def test_render_figure_screenshot_upload_skips_image_api(monkeypatch, tmp_path: Path):
    calls: list[str] = []

    def fake_generate(*args, **kwargs):
        calls.append("called")
        raise AssertionError("screenshot must not call image generation")

    monkeypatch.setattr(
        "app.services.figures.render.dispatcher.generate_figure_image",
        fake_generate,
    )
    book = Book(id=uuid4(), title="Book", book_type=BookType.nonfiction, style_type="")
    fig = Figure(
        id=uuid4(),
        book_id=book.id,
        chapter_index=1,
        figure_type=FigureType.figure,
        raw_annotation="产品界面截图",
        renderer=RENDERER_UPLOAD,
        subtype="screenshot",
        classification_json={"diagram_subtype": "screenshot"},
    )

    with pytest.raises(ValueError, match="手动上传"):
        render_figure(fig, book, tmp_path / "figure.png")

    assert calls == []
