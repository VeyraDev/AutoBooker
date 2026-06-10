"""Visual Brief / Chart Brief / Illustration Brief schema。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VisualBrief:
    diagram_type: str = ""
    title: str = ""
    content_brief: dict[str, Any] = field(default_factory=dict)
    visual_brief: dict[str, Any] = field(default_factory=dict)
    uncertainties: list[Any] = field(default_factory=list)
    compiler_hints: list[Any] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualBrief:
        if not isinstance(data, dict):
            return cls()
        return cls(
            diagram_type=str(data.get("diagram_type") or ""),
            title=str(data.get("title") or ""),
            content_brief=dict(data.get("content_brief") or {}),
            visual_brief=dict(data.get("visual_brief") or {}),
            uncertainties=list(data.get("uncertainties") or []),
            compiler_hints=list(data.get("compiler_hints") or []),
            raw=data,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagram_type": self.diagram_type,
            "title": self.title,
            "content_brief": self.content_brief,
            "visual_brief": self.visual_brief,
            "uncertainties": self.uncertainties,
            "compiler_hints": self.compiler_hints,
        }

    def validate_minimal(self) -> list[str]:
        issues: list[str] = []
        if not self.diagram_type:
            issues.append("missing_diagram_type")
        if not self.title:
            issues.append("missing_title")
        if not self.content_brief:
            issues.append("missing_content_brief")
        return issues
