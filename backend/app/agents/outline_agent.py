"""Generate structured book outline via LLM + jsonschema validation."""

from __future__ import annotations

import json
import logging
from typing import Any

import jsonschema
from jsonschema import ValidationError

from app.llm.client import LLMClient
from app.prompts.outline import (
    OUTLINE_FALLBACK_STYLE,
    OUTLINE_JSON_INSTRUCTION,
    OUTLINE_JSON_SCHEMA,
    OUTLINE_TITLE_RULES,
)
from app.prompts.style_prompts import get_outline_style_prompt
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

class OutlineAgent:
    def __init__(self) -> None:
        self._client = LLMClient()

    @staticmethod
    def _outline_max_tokens(cfg: dict[str, Any]) -> int:
        """大书/多章大纲 JSON 较长，按章数估算 completion 预算。"""
        target = int(cfg.get("target_words") or 80000)
        primary = cfg.get("primary_outline")
        if isinstance(primary, list) and primary:
            chapter_hint = len(primary)
        else:
            chapter_hint = max(8, min(40, target // 8000))
        budget = chapter_hint * 1800 + 6000
        return max(16384, min(budget, 32768))

    @staticmethod
    def build_system_prompt(style_type: str | None) -> str:
        frag = get_outline_style_prompt(style_type or "")
        if not frag.strip():
            frag = OUTLINE_FALLBACK_STYLE
        return frag + "\n\n" + OUTLINE_TITLE_RULES + "\n\n" + OUTLINE_JSON_INSTRUCTION

    def generate(self, book_config: dict[str, Any], reference_snippets: list[str] | None = None, *, model: str | None = None) -> dict[str, Any]:
        reference_snippets = reference_snippets or []
        user_msg = self._build_user_message(book_config, reference_snippets)
        last_err: str | None = None
        system = self.build_system_prompt(book_config.get("style_type"))

        max_tokens = self._outline_max_tokens(book_config)

        for attempt in range(3):
            extra = ""
            if last_err:
                extra = (
                    f"\n\n上次输出无法通过校验（{last_err}）。"
                    "请严格只输出符合要求的 JSON，不要附加说明；"
                    "字符串内的换行请写成 \\n，不要写未转义的双引号；"
                    "使用紧凑 JSON（不要缩进换行）；"
                    "每章 sections 控制在 3-5 节，summary 不超过 50 字。"
                )

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg + extra},
            ]
            raw = self._call_outline_llm(messages, model=model, max_tokens=max_tokens)
            try:
                data = parse_llm_json(raw)
                jsonschema.validate(instance=data, schema=OUTLINE_JSON_SCHEMA)
                return data
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                last_err = str(e)
                logger.warning("outline parse/validate attempt %s failed: %s", attempt + 1, e)

        raise ValueError(f"Outline generation failed after retries: {last_err}")

    def _call_outline_llm(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None,
        max_tokens: int = 16384,
    ) -> str:
        kwargs = {
            "max_tokens": max_tokens,
            "temperature": 0.6,
            "model": model,
            "disable_thinking": True,
        }
        try:
            return self._client.chat_completion(
                messages,
                response_format={"type": "json_object"},
                **kwargs,
            )
        except Exception as exc:
            msg = str(exc).lower()
            if any(token in msg for token in ("response_format", "json_object", "unsupported", "invalid parameter")):
                logger.warning("outline json_object mode unsupported, falling back: %s", exc)
                return self._client.chat_completion(messages, **kwargs)
            raise

    def _build_user_message(self, cfg: dict[str, Any], snippets: list[str]) -> str:
        parts = [
            f"书籍类型：{cfg['book_type']}",
            f"二级体裁（style_type）：{cfg.get('style_type') or '未指定'}",
            f"主题/书名方向：{cfg['topic']}",
            f"目标读者：{cfg.get('target_audience', '大众读者')}",
            f"目标字数：{cfg['target_words']}字",
            f"引用格式：{cfg.get('citation_style', '无需引用')}",
        ]
        if cfg.get("discipline"):
            parts.append(f"学科领域：{cfg['discipline']}")
        if cfg.get("topic_tags"):
            parts.append("三级话题标签：" + "、".join(cfg["topic_tags"]))
        if cfg.get("writing_context"):
            parts.append("【已确认写作上下文】\n" + str(cfg["writing_context"])[:8000])
        if cfg.get("writing_rules"):
            parts.append("全书级写作要求（纳入大纲相关章节要点或全局约束）：\n" + "\n".join(f"- {r}" for r in cfg["writing_rules"][:15]))
        if cfg.get("primary_outline"):
            import json

            parts.append(
                "【用户主大纲 - 必须保留章序与章标题，仅补充摘要、要点、节结构与字数，不得删并重组】\n"
                + json.dumps(cfg["primary_outline"], ensure_ascii=False)[:8000]
            )
        if cfg.get("topic_brief"):
            parts.append("主题补充说明：\n" + str(cfg["topic_brief"])[:6000])
        if snippets:
            parts.append("参考资料摘录（请结合这些内容规划大纲）：")
            parts.extend([f"---\n{s}" for s in snippets[:5]])
        parts.append(
            "再次强调：每章 sections 的 title 必须以「第X节」开头（如 第一节、第二节；每章从一节重新计），"
            "禁止使用 1.1、2.3 等小数编号；禁止冒号对仗式标题，摘要只写在 summary；"
            "preface_brief 必填 2-4 句前言写作要点（散文语气，与主题和大纲结构呼应，不要条目标签）。"
        )
        return "\n".join(parts)
