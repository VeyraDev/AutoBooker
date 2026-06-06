"""Renderer return contract for figure generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FigureRenderResult:
    primary_png_path: Path | None
    render_source: str
    optional_svg_path: Path | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.primary_png_path is not None and self.primary_png_path.is_file()


def coerce_render_result(render_source: str, path: Path, expected_png: Path) -> FigureRenderResult:
    """Adapt legacy renderer tuple output into the new contract."""
    png_path: Path | None = None
    svg_path: Path | None = None
    if path.suffix.lower() == ".svg":
        svg_path = path
        candidate = expected_png.with_suffix(".png")
        if candidate.is_file():
            png_path = candidate
    else:
        png_path = path
        candidate_svg = path.with_suffix(".svg")
        if candidate_svg.is_file():
            svg_path = candidate_svg
    return FigureRenderResult(
        primary_png_path=png_path,
        optional_svg_path=svg_path,
        render_source=render_source,
        diagnostics={
            "legacy_path": str(path),
            "primary_png_present": bool(png_path and png_path.is_file()),
            "svg_present": bool(svg_path and svg_path.is_file()),
        },
    )
