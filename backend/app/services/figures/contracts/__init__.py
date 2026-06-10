"""Diagram Agent 模块间接口契约。"""

from app.services.figures.contracts.geometry_bundle import GeometryBundle
from app.services.figures.contracts.geometry_kinds import geometry_kind_for_subtype
from app.services.figures.contracts.gates import (
    brief_gate,
    design_gate,
    geometry_gate,
    native_gate,
    render_spec_gate,
)
from app.services.figures.contracts.render_spec import assemble_render_spec
from app.services.figures.contracts.renderer_profiles import select_render_profile

__all__ = [
    "GeometryBundle",
    "assemble_render_spec",
    "brief_gate",
    "design_gate",
    "geometry_gate",
    "geometry_kind_for_subtype",
    "native_gate",
    "render_spec_gate",
    "select_render_profile",
]
