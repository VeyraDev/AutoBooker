"""Architecture Native IR schema helpers。"""

from __future__ import annotations

from typing import Any


def empty_architecture_ir() -> dict[str, Any]:
    return {
        "type": "shared_architecture",
        "components": [],
        "containers": [],
        "interactions": [],
        "shared_resources": [],
        "architecture_pattern": "layered",
        "pipeline_stages": [],
    }
