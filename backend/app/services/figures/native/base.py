"""Native IR 容器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NativeIR:
    diagram_type: str
    title: str
    structure: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def native_type(self) -> str:
        return str(self.structure.get("type") or self.diagram_type or "")

    def geometry_kind(self) -> str:
        from app.services.figures.contracts.geometry_kinds import geometry_kind_for_native

        gk = str(self.meta.get("geometry_kind") or self.structure.get("geometry_kind") or "")
        if gk:
            return gk
        return geometry_kind_for_native(self.native_type(), self.diagram_type)

    def with_geometry_kind(self, kind: str) -> NativeIR:
        self.meta["geometry_kind"] = kind
        self.structure["geometry_kind"] = kind
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagram_type": self.diagram_type,
            "title": self.title,
            "native_structure": self.structure,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NativeIR:
        structure = dict(data.get("native_structure") or data.get("structure") or data)
        dtype = str(data.get("diagram_type") or structure.get("type") or "flow")
        title = str(data.get("title") or structure.get("title") or "示意图")
        if "type" not in structure:
            structure["type"] = dtype
        meta = dict(data.get("meta") or {})
        return cls(diagram_type=dtype, title=title, structure=structure, meta=meta)
