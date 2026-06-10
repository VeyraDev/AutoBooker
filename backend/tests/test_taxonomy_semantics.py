"""分类树语义解析：一级分为 / A下面 层级保留。"""

from __future__ import annotations

from app.services.figures.parse.taxonomy import _rule_tree, _to_graph, prefer_taxonomy_spec
from app.services.figures.pipeline.structured_run import run_structured_pipeline
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext


def test_rule_tree_parses_level1_and_level2():
    text = (
        "大语言模型分类图，一级分为开源模型与闭源模型两类，"
        "开源模型下面有GPT-4、LLaMA、Qwen；闭源模型下面有Claude、Gemini"
    )
    intent = DiagramIntent("knowledge", "taxonomy_map", title="大语言模型分类图", diagram_type="taxonomy")
    root, children = _rule_tree(text, intent)
    assert root == "大语言模型"
    labels = {c["label"] for c in children}
    assert "开源模型" in labels or "开源" in labels
    assert "闭源模型" in labels or "闭源" in labels
    open_branch = next(c for c in children if "开源" in c["label"])
    closed_branch = next(c for c in children if "闭源" in c["label"])
    open_kids = {g["label"] for g in open_branch.get("children") or []}
    closed_kids = {g["label"] for g in closed_branch.get("children") or []}
    assert "GPT-4" in open_kids
    assert "LLaMA" in open_kids
    assert "Claude" in closed_kids


def test_ai_tech_stack_three_level_hierarchy():
    """用户场景：感知/认知/行动 各挂自己的二级子类，禁止全挂到第一个一级节点。"""
    text = (
        "AI技术栈分类，一级分为感知、认知、行动三类，"
        "感知下分图像识别和语音识别，认知下分自然语言处理和知识推理，"
        "行动下分机器人控制和决策优化"
    )
    intent = DiagramIntent("knowledge", "taxonomy_map", title="AI技术栈分类", diagram_type="taxonomy")
    root, children = _rule_tree(text, intent)
    assert root == "AI技术栈分类"
    by_label = {c["label"]: c for c in children}
    assert set(by_label) == {"感知", "认知", "行动"}
    assert {g["label"] for g in by_label["感知"]["children"]} == {"图像识别", "语音识别"}
    assert {g["label"] for g in by_label["认知"]["children"]} == {"自然语言处理", "知识推理"}
    assert {g["label"] for g in by_label["行动"]["children"]} == {"机器人控制", "决策优化"}

    spec = _to_graph("AI技术栈分类", root, children)
    edges = {(e["from"], e["to"]) for e in spec["edges"]}
    assert ("c0", "c0_0") in edges and ("c0", "c0_1") in edges
    assert ("c1", "c1_0") in edges and ("c1", "c1_1") in edges
    assert ("c2", "c2_0") in edges and ("c2", "c2_1") in edges
    assert not any(e[0] == "c0" and e[1].startswith("c1_") for e in edges)
    assert prefer_taxonomy_spec(spec, text)


def test_to_graph_edges_are_parent_child_not_star_to_leaves():
    text = "AI技术栈分类，一级分为感知、认知、行动三类，感知下面有图像识别、语音识别"
    intent = DiagramIntent("knowledge", "taxonomy_map", title="AI技术栈分类", diagram_type="taxonomy")
    root, children = _rule_tree(text, intent)
    spec = _to_graph("AI技术栈分类", root, children)
    edges = {(e["from"], e["to"]) for e in spec["edges"]}
    assert ("root", "c0") in edges or any(e[0] == "root" for e in edges)
    assert not all(e[0] == "root" for e in edges if e[1].startswith("c0_") or e[1].startswith("c1_"))
    assert prefer_taxonomy_spec(spec, text)


def test_structured_pipeline_uses_taxonomy_compiler_for_hierarchy_text():
    from unittest.mock import patch

    from app.services.figures.brief.schema import VisualBrief

    ctx = PipelineContext(
        description="分类",
        normalized_input=(
            "大语言模型分类图，一级分为开源与闭源，开源下有GPT-4、LLaMA，闭源下有Claude"
        ),
        use_llm=True,
        model="dummy",
    )
    intent = DiagramIntent("knowledge", "taxonomy_map", 0.9, "test", "大语言模型分类", diagram_type="taxonomy")
    brief = VisualBrief(
        diagram_type="taxonomy",
        title="大语言模型分类",
        content_brief={
            "root": "大语言模型",
            "children": [
                {"name": "开源", "children": [{"name": "GPT-4"}, {"name": "LLaMA"}]},
                {"name": "闭源", "children": [{"name": "Claude"}]},
            ],
        },
        visual_brief={"layout_intent": "balanced_tree"},
    )
    understanding = {
        "goal": "show_taxonomy",
        "route": "structured_diagram",
        "candidate_diagrams": [{"type": "taxonomy_map", "score": 0.95, "reason": "分类"}],
    }
    with patch("app.services.figures.pipeline.structured_run.extract_visual_brief", return_value=brief):
        _, parsed, _, _, flags, bundle = run_structured_pipeline(ctx, intent, understanding=understanding)

    assert bundle.get("native_ir")
    assert "grammar_blocked" not in flags
    assert len(parsed.parsed_spec.get("nodes") or []) >= 3
