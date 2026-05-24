"""章节/书稿审校：结构化问题列表与修改建议。"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.client import LLMClient
from app.prompts.publication_standards import CHAPTER_PUBLICATION_STANDARDS
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

REVIEW_SYSTEM = """你是一位资深图书审校编辑，熟悉中文非虚构与学术专著的出版规范。
请对提交的章节正文做专业审校，输出严格 JSON（不要 markdown 代码块外的任何文字）。

输出 schema：
{
  "summary": "200字以内整体评价",
  "score": 0-100 的整数质量分,
  "issues": [
    {
      "id": "1",
      "severity": "high|medium|low",
      "category": "logic|style|grammar|citation|structure|other",
      "title": "问题标题（15字内）",
      "detail": "问题说明",
      "quote": "原文中有问题的片段（尽量逐字引用，无则空字符串）",
      "suggestion": "具体修改建议或可替换表述"
    }
  ]
}

要求：
- issues 按严重程度排序，最多 12 条；无重大问题时 issues 可为空数组
- high：事实错误、逻辑矛盾、严重语病；medium：表达、衔接、格式；low：润色级建议
- 勿编造书中不存在的内容；quote 必须来自给定正文
"""


class ReviewAgent:
    def __init__(self, *, model: str) -> None:
        self._model = model
        self._client = LLMClient()

    def review_chapter(
        self,
        *,
        chapter_title: str,
        body: str,
        book_title: str,
        book_type: str,
        citation_style: str,
        user_material: str = "",
    ) -> dict[str, Any]:
        text = (body or "").strip()
        if not text:
            return {
                "summary": "本章暂无正文，无法审校。",
                "score": 0,
                "issues": [],
            }

        truncated = text[:28_000]
        user_parts = [
            f"书名：{book_title or '未命名'}",
            f"类型：{book_type}",
            f"引用格式要求：{citation_style}",
            f"章节标题：{chapter_title}",
            CHAPTER_PUBLICATION_STANDARDS,
        ]
        if user_material.strip():
            user_parts.append(f"作者写作约束（审校时参考）：\n{user_material[:3000]}")
        user_parts.append(f"【待审校正文】\n{truncated}")

        raw = self._client.chat_completion(
            [
                {"role": "system", "content": REVIEW_SYSTEM},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            model=self._model,
            max_tokens=4096,
            temperature=0.35,
            provider="writer",
        )
        try:
            data = parse_llm_json(raw)
        except Exception as e:
            logger.warning("review JSON parse failed: %s", e)
            return {
                "summary": "审校结果解析失败，请重试。",
                "score": 0,
                "issues": [],
            }

        issues = data.get("issues") or []
        if not isinstance(issues, list):
            issues = []
        normalized: list[dict[str, Any]] = []
        for i, item in enumerate(issues[:12]):
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": str(item.get("id") or i + 1),
                    "severity": _enum_val(item.get("severity"), ("high", "medium", "low"), "medium"),
                    "category": _enum_val(
                        item.get("category"),
                        ("logic", "style", "grammar", "citation", "structure", "other"),
                        "other",
                    ),
                    "title": str(item.get("title") or "待改进")[:80],
                    "detail": str(item.get("detail") or "")[:2000],
                    "quote": str(item.get("quote") or "")[:500],
                    "suggestion": str(item.get("suggestion") or "")[:2000],
                }
            )

        score = data.get("score", 0)
        try:
            score = max(0, min(100, int(score)))
        except (TypeError, ValueError):
            score = 70

        return {
            "summary": str(data.get("summary") or "")[:1500],
            "score": score,
            "issues": normalized,
        }


def _enum_val(raw: Any, allowed: tuple[str, ...], default: str) -> str:
    s = str(raw or "").strip().lower()
    return s if s in allowed else default
