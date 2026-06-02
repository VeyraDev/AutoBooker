"""Transformer 架构解析。"""

from __future__ import annotations

import re

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析 Transformer 架构图 JSON：
{{
  "encoder_layers": 6,
  "decoder_layers": 6,
  "components": ["self_attention","cross_attention","ffn","layer_norm","residual"],
  "title": "Transformer 编码器-解码器架构"
}}
只输出 JSON。描述：{text}
"""


def parse_transformer(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    model = (ctx.model or settings.intent_model).strip()
    if ctx.use_llm and model:
        try:
            out = LLMClient().chat_completion(
                [{"role": "user", "content": _PROMPT.format(text=ctx.normalized_input[:2000])}],
                model=model,
                max_tokens=1024,
                temperature=0.2,
            )
            data = parse_llm_json(out)
            if isinstance(data, dict):
                data.setdefault("title", intent.title or "Transformer 编码器-解码器架构")
                return ParsedDiagram(data, "llm_transformer")
        except Exception:
            pass
    n = 6
    m = re.search(r"(\d+)\s*层", ctx.normalized_input)
    if m:
        n = max(1, min(12, int(m.group(1))))
    return ParsedDiagram(
        {
            "encoder_layers": n,
            "decoder_layers": n,
            "components": ["self_attention", "cross_attention", "ffn", "layer_norm", "residual"],
            "title": intent.title or "Transformer 编码器-解码器架构",
        },
        "rules_transformer",
    )
