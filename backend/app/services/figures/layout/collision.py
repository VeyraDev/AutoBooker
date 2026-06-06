"""节点重叠检测与微调。"""

from __future__ import annotations

from app.services.figures.layout.schema import LayoutResult, NodePosition

_GAP = 16.0


def resolve_collisions(layout: LayoutResult) -> list[str]:
    warnings: list[str] = []
    positions = list(layout.node_positions.values())
    for i, a in enumerate(positions):
        for b in positions[i + 1:]:
            if _overlap(a, b):
                b.y = a.y + a.height + _GAP
                warnings.append(f"collision_shift:{b.id}")
    return warnings


def _overlap(a: NodePosition, b: NodePosition) -> bool:
    return not (
        a.x + a.width + _GAP <= b.x
        or b.x + b.width + _GAP <= a.x
        or a.y + a.height + _GAP <= b.y
        or b.y + b.height + _GAP <= a.y
    )
