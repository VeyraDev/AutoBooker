"""Flow Native IR schema helpers。"""

from __future__ import annotations

from typing import Any


def empty_flow_ir() -> dict[str, Any]:
    return {
        "type": "process_flow",
        "steps": [],
        "parallel_groups": [],
        "joins": [],
        "decisions": [],
        "loops": [],
        "dependencies": [],
        "optional_branches": [],
        "interrupt_branches": [],
    }
