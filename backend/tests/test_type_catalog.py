"""配图类型目录完整性：每种规范类型必须有 renderer / parser / 布局（如适用）。"""

from __future__ import annotations

from app.services.figures.catalog.type_catalog import (
    CANONICAL_SUBTYPES,
    FIGURE_TYPE_CATALOG,
    build_candidate_type_map,
    validate_catalog,
)
from app.services.figures.intent.taxonomy import SUBTYPE_TO_RENDERER


def test_canonical_subtype_count_matches_docs():
    # V3 文档主枚举 + chart / screenshot
    assert len(CANONICAL_SUBTYPES) == 12


def test_every_canonical_has_renderer_and_pipeline():
    for subtype, spec in FIGURE_TYPE_CATALOG.items():
        assert spec.renderer
        assert spec.pipeline in {"structured", "chart", "illustration", "upload"}
        assert spec.family
        if spec.pipeline == "structured":
            assert spec.parser, f"{subtype} 缺少 parser"
            assert spec.layout_policy_key, f"{subtype} 缺少 layout_policy_key"
        if spec.pipeline == "chart":
            assert spec.renderer.endswith("chart")
        if spec.pipeline == "illustration":
            assert spec.renderer == "illustration.image_api"
        if spec.pipeline == "upload":
            assert spec.renderer == "upload"


def test_aliases_map_to_canonical_not_new_types():
    cmap = build_candidate_type_map()
    for alias, (family, canonical) in cmap.items():
        assert canonical in CANONICAL_SUBTYPES, f"别名 {alias} 指向未知类型 {canonical}"
        assert FIGURE_TYPE_CATALOG[canonical].family == family


def test_subtype_to_renderer_covers_catalog():
    for subtype in CANONICAL_SUBTYPES:
        assert subtype in SUBTYPE_TO_RENDERER


def test_validate_catalog_no_critical_issues():
    issues = validate_catalog()
    # diagram_type 与 taxonomy 个别历史别名允许差异，不应有 parser/renderer 缺失
    critical = [i for i in issues if "parser" in i or "renderer 未" in i]
    assert not critical, critical
