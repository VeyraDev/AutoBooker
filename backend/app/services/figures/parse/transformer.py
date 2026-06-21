"""旧双栈机制图 parser 兼容层。"""

from __future__ import annotations

import re

from app.services.figures.parse.mechanism import _layer_count, _short, _title, _to_graph
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext

_TRANSFORMER_ENCODER = ["multi_head_self_attention", "add_norm", "feed_forward", "add_norm"]
_TRANSFORMER_DECODER = [
    "masked_multi_head_self_attention",
    "add_norm",
    "cross_attention",
    "add_norm",
    "feed_forward",
    "add_norm",
]


def _is_transformer_request(ctx: PipelineContext, intent: DiagramIntent) -> bool:
    text = f"{intent.diagram_subtype} {intent.title} {ctx.normalized_input}".lower()
    return "transformer" in text or "编码器" in text or "解码器" in text


def _transformer_spec(ctx: PipelineContext, intent: DiagramIntent) -> dict:
    n = _layer_count(ctx.normalized_input)
    title = _title(intent, ctx.normalized_input) or "双栈机制结构图"
    return {
        "diagram_subtype": "transformer",
        "title": title,
        "encoder_layers": n,
        "decoder_layers": n,
        "encoder": {"layers": list(_TRANSFORMER_ENCODER)},
        "decoder": {"layers": list(_TRANSFORMER_DECODER)},
        "connections": [{"from": "encoder.output", "to": "decoder.cross_attention", "type": "cross_attention"}],
        "components": list(dict.fromkeys(_TRANSFORMER_ENCODER + _TRANSFORMER_DECODER + ["residual"])),
        "structure_summary": "机制语法：左右堆叠模块 + 交叉连接",
    }


def parse_transformer(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    if _is_transformer_request(ctx, intent):
        return ParsedDiagram(_transformer_spec(ctx, intent), "rules_transformer")
    from app.services.figures.parse.mechanism import parse_mechanism

    return parse_mechanism(ctx, intent)
