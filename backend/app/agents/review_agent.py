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
      "category": "logic|style|grammar|citation|structure|hallucination|figure|other",
      "title": "问题标题（15字内）",
      "detail": "问题说明",
      "quote": "原文中有问题的片段（尽量逐字引用，无则空字符串）",
      "suggestion": "见 action_type 说明",
      "action_type": "replace|delete|insert|revise"
    }
  ]
}

action_type 含义（必须准确分类）：
- replace：suggestion 为**可直接替换 quote 的完整改写句/段**（不含「改为」「建议」等说明语）
- delete：删除 quote 指出的片段，suggestion 留空
- insert：在 quote 锚点附近**新增**内容，suggestion 为要插入的完整句子（不是操作说明）
- revise：suggestion 为**给编辑/AI 的操作说明**（如「统一使用我们」「改为不涉及代码」），不可直接当正文替换

要求：
- issues 按严重程度排序，最多 12 条；无重大问题时 issues 可为空数组
- high：事实错误、逻辑矛盾、严重语病、无来源的具体数据/案例、未入库引用；medium：表达、衔接、格式；low：润色级建议
- 重点检查：无来源断言（「研究表明」等）、人名+时间+地点齐全但无出处的「案例」、与【已批准引用库】不一致的引用、图表占位与正文不一致
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
        approved_citations: list[str] | None = None,
        figure_summaries: list[str] | None = None,
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
        if approved_citations:
            user_parts.append(
                "【已批准引用库】\n" + "\n".join(approved_citations[:200])
            )
        if figure_summaries:
            user_parts.append(
                "【本章图表】\n" + "\n".join(figure_summaries[:30])
            )
        user_parts.append(f"【待审校正文】\n{truncated}")

        raw = self._client.chat_completion(
            [
                {"role": "system", "content": REVIEW_SYSTEM},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            model=self._model,
            max_tokens=4096,
            temperature=0.35,
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
                        (
                            "logic",
                            "style",
                            "grammar",
                            "citation",
                            "structure",
                            "hallucination",
                            "figure",
                            "other",
                        ),
                        "other",
                    ),
                    "title": str(item.get("title") or "待改进")[:80],
                    "detail": str(item.get("detail") or "")[:2000],
                    "quote": str(item.get("quote") or "")[:500],
                    "suggestion": str(item.get("suggestion") or "")[:2000],
                    "action_type": _enum_val(
                        item.get("action_type"),
                        ("replace", "delete", "insert", "revise"),
                        _infer_action_type(
                            str(item.get("quote") or ""),
                            str(item.get("suggestion") or ""),
                        ),
                    ),
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


def _infer_action_type(quote: str, suggestion: str) -> str:
    q = quote.strip()
    s = suggestion.strip()
    if q and not s:
        return "delete"
    if not q and s:
        return "insert"
    if not q:
        return "revise"
    instr_markers = (
        "统一",
        "建议",
        "改为",
        "或改为",
        "应该",
        "可以",
        "不宜",
        "避免",
        "增加",
        "删除",
        "补充",
        "勿",
        "不要",
    )
    if len(s) > 100 or "……" in s or "..." in s:
        if any(m in s for m in instr_markers):
            return "revise"
    if any(s.startswith(m) for m in instr_markers):
        return "revise"
    if "，或" in s or "；或" in s:
        return "revise"
    return "replace"
