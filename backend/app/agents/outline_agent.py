"""Generate structured book outline via LLM + jsonschema validation."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import ValidationError

from app.llm.client import LLMClient
from app.prompts.outline import OUTLINE_JSON_SCHEMA, OUTLINE_SYSTEM_PROMPT
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_DEBUG_LOG = Path(__file__).resolve().parents[4] / "debug-7c6f39.log"


def _agent_ndjson(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "7c6f39",
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data,
            "hypothesisId": hypothesis_id,
        }
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


class OutlineAgent:
    def __init__(self) -> None:
        self._client = LLMClient()

    def generate(self, book_config: dict[str, Any], reference_snippets: list[str] | None = None) -> dict[str, Any]:
        reference_snippets = reference_snippets or []
        user_msg = self._build_user_message(book_config, reference_snippets)
        last_err: str | None = None

        for attempt in range(3):
            extra = ""
            if last_err:
                extra = f"\n\n上次输出无法通过校验（{last_err}）。请严格只输出符合要求的 JSON，不要附加说明。"

            messages = [
                {"role": "system", "content": OUTLINE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg + extra},
            ]
            raw = self._client.chat_completion(
                messages,
                max_tokens=4096,
                temperature=0.6,
                provider="writer",
            )
            try:
                data = parse_llm_json(raw)
                jsonschema.validate(instance=data, schema=OUTLINE_JSON_SCHEMA)
                _agent_ndjson(
                    "outline_agent.py:generate",
                    "validate_ok",
                    {"attempt": attempt + 1, "raw_len": len(raw), "chapters_n": len(data.get("chapters") or [])},
                    "H3",
                )
                return data
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                last_err = str(e)
                _agent_ndjson(
                    "outline_agent.py:generate",
                    "parse_validate_fail",
                    {"attempt": attempt + 1, "raw_len": len(raw), "err": str(e)[:400]},
                    "H3",
                )
                logger.warning("outline parse/validate attempt %s failed: %s", attempt + 1, e)

        _agent_ndjson(
            "outline_agent.py:generate",
            "all_retries_failed",
            {"last_err": (last_err or "")[:500]},
            "H3",
        )
        raise ValueError(f"Outline generation failed after retries: {last_err}")

    def _build_user_message(self, cfg: dict[str, Any], snippets: list[str]) -> str:
        parts = [
            f"书籍类型：{cfg['book_type']}",
            f"主题/书名方向：{cfg['topic']}",
            f"目标读者：{cfg.get('target_audience', '大众读者')}",
            f"目标字数：{cfg['target_words']}字",
            f"引用格式：{cfg.get('citation_style', '无需引用')}",
        ]
        if cfg.get("discipline"):
            parts.append(f"学科领域：{cfg['discipline']}")
        if snippets:
            parts.append("参考资料摘录（请结合这些内容规划大纲）：")
            parts.extend([f"---\n{s}" for s in snippets[:5]])
        return "\n".join(parts)
