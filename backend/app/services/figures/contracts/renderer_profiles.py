"""Renderer Profile 注册与分派。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.figures.contracts.geometry_kinds import (
    GEOMETRY_BLOCKS,
    GEOMETRY_GRAPH,
    GEOMETRY_LANES,
    GEOMETRY_MATRIX,
    GEOMETRY_TIMELINE,
    GEOMETRY_TREE,
)
from app.services.figures.contracts.graph_visual_grammar import render_profile_for_graph_grammar


@dataclass(frozen=True)
class RendererProfile:
    id: str
    geometry_kinds: tuple[str, ...]
    variants: tuple[str, ...]
    requires: tuple[str, ...]
    priority: int = 10


PROFILES: tuple[RendererProfile, ...] = (
    RendererProfile("svg.matrix", (GEOMETRY_MATRIX,), ("matrix", "cards", "pros_cons", "scoreboard", "default"), ("extensions",), 100),
    RendererProfile("svg.timeline", (GEOMETRY_TIMELINE,), ("timeline", "default"), ("events",), 100),
    RendererProfile("svg.blocks", (GEOMETRY_BLOCKS,), ("cards", "default"), ("blocks",), 100),
    RendererProfile("svg.swimlane", (GEOMETRY_LANES,), ("swimlane", "default"), ("lanes", "nodes"), 100),
    RendererProfile("svg.tree", (GEOMETRY_TREE,), ("tree", "default"), ("root", "children"), 90),
    RendererProfile("svg.flow", (GEOMETRY_GRAPH,), ("flow", "default"), ("nodes",), 90),
    RendererProfile("svg.architecture", (GEOMETRY_GRAPH,), ("architecture", "pipeline", "default"), ("nodes",), 90),
    RendererProfile("svg.mechanism", (GEOMETRY_GRAPH,), ("mechanism", "default"), ("nodes",), 90),
    RendererProfile("svg.radial", (GEOMETRY_GRAPH,), ("default",), ("nodes",), 90),
    RendererProfile("svg.network", (GEOMETRY_GRAPH,), ("default",), ("nodes",), 90),
    RendererProfile("svg.decision", (GEOMETRY_GRAPH,), ("flow", "default"), ("nodes",), 90),
    RendererProfile("svg.graph", (GEOMETRY_GRAPH,), ("flow", "architecture", "pipeline", "mechanism", "default"), ("nodes",), 50),
    RendererProfile("mpl.timeline", (GEOMETRY_TIMELINE,), ("timeline",), ("events",), 20),
    RendererProfile("mpl.taxonomy", (GEOMETRY_TREE,), ("tree",), ("root",), 20),
)


def select_render_profile(spec: dict[str, Any]) -> str:
    explicit = str(spec.get("render_profile") or "")
    if explicit:
        return explicit

    gk = str(spec.get("geometry_kind") or "")
    variant = str((spec.get("design_spec") or {}).get("component_variant") or "default")
    if gk == GEOMETRY_GRAPH:
        grammar_profile = render_profile_for_graph_grammar(str(spec.get("graph_visual_grammar") or ""))
        if grammar_profile and spec.get("nodes"):
            return grammar_profile

    if not gk:
        gk = _infer_geometry(spec)
        if gk == GEOMETRY_GRAPH:
            grammar_profile = render_profile_for_graph_grammar(str(spec.get("graph_visual_grammar") or ""))
            if grammar_profile and spec.get("nodes"):
                return grammar_profile

    candidates = [p for p in PROFILES if gk in p.geometry_kinds]
    candidates.sort(key=lambda p: -p.priority)

    for profile in candidates:
        if variant not in profile.variants and "default" not in profile.variants:
            continue
        if _has_required(spec, profile):
            return profile.id

    if gk == GEOMETRY_MATRIX:
        return "svg.matrix"
    if gk == GEOMETRY_TIMELINE:
        return "svg.timeline"
    if gk == GEOMETRY_BLOCKS:
        return "svg.blocks"
    if gk == GEOMETRY_LANES:
        return "svg.swimlane"
    if gk == GEOMETRY_TREE:
        return "svg.tree"
    return "svg.graph"


def _infer_geometry(spec: dict[str, Any]) -> str:
    if spec.get("cells") or spec.get("dimensions"):
        return GEOMETRY_MATRIX
    if spec.get("events"):
        return GEOMETRY_TIMELINE
    if spec.get("blocks"):
        return GEOMETRY_BLOCKS
    if spec.get("lanes"):
        return GEOMETRY_LANES
    if spec.get("children") and spec.get("root"):
        return GEOMETRY_TREE
    return GEOMETRY_GRAPH


def _has_required(spec: dict[str, Any], profile: RendererProfile) -> bool:
    for field in profile.requires:
        if field == "extensions":
            if not spec.get("extensions"):
                return False
        elif field == "events":
            if not (spec.get("events") or (spec.get("extensions") or {}).get("events")):
                return False
        elif field == "blocks":
            if not (spec.get("blocks") or (spec.get("extensions") or {}).get("blocks")):
                return False
        elif field == "nodes":
            if not spec.get("nodes"):
                return False
        elif field == "lanes":
            if not (spec.get("lanes") or (spec.get("extensions") or {}).get("lanes")):
                return False
        elif field == "root":
            if not (spec.get("root") or (spec.get("extensions") or {}).get("root")):
                return False
        elif field == "children":
            if not (spec.get("children") or (spec.get("extensions") or {}).get("children")):
                return False
    return True
