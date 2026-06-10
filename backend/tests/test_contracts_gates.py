"""契约：校验闸门。"""

from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.contracts.gates import brief_gate, native_gate, render_spec_gate
from app.services.figures.native.base import NativeIR


def test_brief_gate_invalid():
    brief = VisualBrief(diagram_type="", title="", content_brief={})
    assert "brief_invalid" in brief_gate(brief)


def test_native_gate_empty_structure():
    native = NativeIR(diagram_type="flow", title="t", structure={})
    native.meta["compiler_fallback_blocked"] = True
    flags = native_gate(native)
    assert "compiler_fallback_blocked" in flags
    assert "native_invalid" in flags


def test_render_spec_gate_matrix_sparse():
    spec = {
        "geometry_kind": "matrix",
        "extensions": {"subjects": ["A"], "dimensions": ["D"], "cells": []},
    }
    flags = render_spec_gate(spec)
    assert "cells_sparse" in flags
