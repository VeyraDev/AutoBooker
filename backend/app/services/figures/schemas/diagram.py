"""配图 V2 数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineContext:
    description: str
    normalized_input: str = ""
    book_type: str = ""
    style_type: str = ""
    chapter_title: str = ""
    user_hint: str = ""
    legacy_tag: str | None = None
    subtype_hint: str | None = None
    model: str = ""
    use_llm: bool = True


@dataclass
class DiagramIntent:
    diagram_family: str
    diagram_subtype: str
    confidence: float = 0.7
    source: str = "rules"
    title: str = ""


@dataclass
class ParsedDiagram:
    parsed_spec: dict[str, Any] = field(default_factory=dict)
    source: str = "parser"


@dataclass
class VisualPlan:
    layout: str = ""
    style: str = ""
    visual_description: str = ""
    must_include: list[str] = field(default_factory=list)
    must_avoid: list[str] = field(default_factory=list)

    def to_prompt_spec(self) -> dict[str, Any]:
        return {
            "layout": self.layout,
            "style": self.style,
            "visual_description": self.visual_description,
            "must_include": self.must_include,
            "must_avoid": self.must_avoid,
        }


@dataclass
class ClassificationRecord:
    diagram_family: str
    diagram_subtype: str
    renderer: str
    confidence: float
    understanding_source: str
    normalized_input: str
    parsed_spec: dict[str, Any]
    visual_plan: dict[str, Any] | None
    prompt_spec: dict[str, Any]
    image_type: str = ""
    subtype: str = ""
    style_profile: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "diagram_family": self.diagram_family,
            "diagram_subtype": self.diagram_subtype,
            "renderer": self.renderer,
            "confidence": self.confidence,
            "understanding_source": self.understanding_source,
            "normalized_input": self.normalized_input,
            "parsed_spec": self.parsed_spec,
            "visual_plan": self.visual_plan,
            "prompt_spec": self.prompt_spec,
            "image_type": self.image_type,
            "subtype": self.subtype,
            "style_profile": self.style_profile,
        }
