from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.services.figures.render.compositor import render_composited_diagram


def test_generic_compositor_renders_branch_png(tmp_path: Path):
    spec = {
        "title": "甲乙丙流程",
        "diagram_subtype": "process_flow",
        "nodes": [
            {"id": "a", "label": "甲"},
            {"id": "b", "label": "乙"},
            {"id": "c", "label": "丙"},
            {"id": "d", "label": "丁"},
        ],
        "edges": [
            {"from": "a", "to": "b"},
            {"from": "a", "to": "c"},
            {"from": "b", "to": "d"},
            {"from": "c", "to": "d"},
        ],
    }

    result = render_composited_diagram(spec, tmp_path / "figure.png", subtype="process_flow", title="甲乙丙流程")

    assert result.render_source == "generic.compositor"
    assert result.optional_svg_path is None
    assert result.primary_png_path and result.primary_png_path.is_file()
    assert result.diagnostics["layout"] == "branch"
    with Image.open(result.primary_png_path) as image:
        assert image.size == (1365, 900)


def test_compositor_has_no_domain_templates():
    source = Path("app/services/figures/render/compositor/renderer.py").read_text(encoding="utf-8")
    forbidden = ("RAG", "Transformer", "transfer", "vLLM", "LangChain")
    assert not any(word in source for word in forbidden)
