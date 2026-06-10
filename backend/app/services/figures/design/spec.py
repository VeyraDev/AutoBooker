"""Design Spec schema。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DesignSpec:
    theme: str = "modern_saas"
    component_variant: str = "default"
    container_style: str = "rounded"
    arrow_style: str = "orthogonal"
    annotation_style: str = "minimal"
    tokens: dict[str, Any] = field(default_factory=dict)
    readability: dict[str, Any] = field(default_factory=lambda: {
        "min_contrast_ratio": 4.5,
        "max_label_lines": 4,
        "truncation_policy": "wrap",
        "locale": "mixed",
    })

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "component_variant": self.component_variant,
            "container_style": self.container_style,
            "arrow_style": self.arrow_style,
            "annotation_style": self.annotation_style,
            "tokens": self.tokens,
            "readability": dict(self.readability),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DesignSpec:
        default_readability = {
            "min_contrast_ratio": 4.5,
            "max_label_lines": 4,
            "truncation_policy": "wrap",
            "locale": "mixed",
        }
        rb = dict(default_readability)
        if isinstance(data.get("readability"), dict):
            rb.update(data["readability"])
        return cls(
            theme=str(data.get("theme") or "modern_saas"),
            component_variant=str(data.get("component_variant") or "default"),
            container_style=str(data.get("container_style") or "rounded"),
            arrow_style=str(data.get("arrow_style") or "orthogonal"),
            annotation_style=str(data.get("annotation_style") or "minimal"),
            tokens=dict(data.get("tokens") or {}),
            readability=rb,
        )
