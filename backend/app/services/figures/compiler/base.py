"""Compiler 基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent


class DiagramCompiler(ABC):
    @abstractmethod
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR | None:
        ...

    def compile_content(self, content: dict[str, Any], brief: VisualBrief, intent: DiagramIntent) -> NativeIR | None:
        return self.compile(brief, intent)
