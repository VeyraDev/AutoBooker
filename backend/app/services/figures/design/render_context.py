"""Design Spec → 渲染上下文。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.figures.design.arrow_styles import ArrowStyle, get_arrow_style
from app.services.figures.design.container_styles import ContainerStyle, get_container_style
from app.services.figures.design.spec import DesignSpec
from app.services.figures.design.tokens import DesignTokens, tokens_for_theme
from app.services.figures.design.variants import get_variant_config
from app.services.figures.design.variants.base import VariantStyle


@dataclass
class RenderContext:
    tokens: DesignTokens
    variant: VariantStyle
    arrow: ArrowStyle
    container: ContainerStyle
    annotation_style: str = "minimal"
    density: str = "medium"
    reading_order: str = "top_to_bottom"
    theme: str = "modern_saas"
    component_variant: str = "default"
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def comparison_template(self) -> str | None:
        tpl = self.variant.extras.get("template")
        if tpl in {"matrix", "cards", "pros_cons", "scoreboard", "bar_horizontal", "radar"}:
            return str(tpl)
        if self.component_variant in {"matrix", "cards", "pros_cons", "scoreboard", "bar_horizontal", "radar"}:
            return self.component_variant
        return None

    def node_radius(self) -> int:
        return self.variant.node_radius or self.tokens.node_radius

    def edge_width(self) -> float:
        return self.tokens.edge_width * self.variant.edge_width_scale * self.arrow.width_scale

    def resolve_node_fill(self, kind: str, meta: dict[str, Any], palette: dict[str, str]) -> str:
        if meta.get("color"):
            return str(meta["color"])
        semantic = {
            "decision": palette.get("decision", self.tokens.decision_fill),
            "gateway": palette.get("gateway", self.tokens.gateway_fill),
            "database": palette.get("database", self.tokens.card),
            "queue": palette.get("queue", self.tokens.card),
            "model": palette.get("model", palette.get("secondary", self.tokens.primary)),
            "service": palette.get("service", self.tokens.node_fill),
            "warning": palette.get("warning", "#FEE2E2"),
            "success": palette.get("success", "#DCFCE7"),
        }
        if kind in semantic:
            return semantic[kind]
        key = self.variant.node_fill_key
        return palette.get(key, self.tokens.node_fill)

    def resolve_text_fill(self, bg_fill: str) -> str:
        """根据背景色选择可读文字色。"""
        dark_text = self.tokens.text
        light_text = "#FFFFFF"
        bg = (bg_fill or "").upper()
        dark_bgs = {"#2563EB", "#1E3A5F", "#1E40AF", "#1D4ED8"}
        if bg in dark_bgs or bg_fill == self.tokens.primary:
            return light_text
        return dark_text


def build_render_context(design_spec: DesignSpec | dict[str, Any] | None) -> RenderContext:
    spec = design_spec if isinstance(design_spec, DesignSpec) else DesignSpec.from_dict(design_spec or {})
    tokens = tokens_for_theme(spec.theme)
    variant = get_variant_config(spec.component_variant)
    arrow = get_arrow_style(spec.arrow_style)
    container = get_container_style(spec.container_style)
    tok = dict(spec.tokens or {})
    if tok.get("density") == "high":
        tokens.node_radius = max(4, tokens.node_radius - 2)
        tokens.font_size = max(11, tokens.font_size - 1)
    elif tok.get("density") == "low":
        tokens.node_radius += 2
        tokens.font_size += 1
    return RenderContext(
        tokens=tokens,
        variant=variant,
        arrow=arrow,
        container=container,
        annotation_style=spec.annotation_style,
        density=str(tok.get("density") or "medium"),
        reading_order=str(tok.get("reading_order") or "top_to_bottom"),
        theme=spec.theme,
        component_variant=spec.component_variant,
        extras={**dict(variant.extras), **{k: v for k, v in tok.items() if k in {"visual_directives", "directive_ids"}}},
    )
