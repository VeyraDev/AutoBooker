"""章节/书稿审校：结构化问题列表与修改建议。"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.client import LLMClient
from app.prompts.publication_standards import CHAPTER_PUBLICATION_STANDARDS
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

MAX_ISSUES = 12
MAX_CHUNK_ISSUES = 30

REVIEW_SYSTEM = """你是一位资深图书审校编辑，熟悉中文非虚构与学术专著的出版规范。
请对提交的章节正文做专业审校，输出严格 JSON（不要 markdown 代码块外的任何文字）。

输出 schema：
{
  "summary": "200字以内整体评价",
  "dimensions": [
    {"key": "logic_structure", "raw_score": 0-100, "confidence": 0-1, "summary": "逻辑结构简评"},
    {"key": "language_grammar", "raw_score": 0-100, "confidence": 0-1, "summary": "语言语法简评"},
    {"key": "style_consistency", "raw_score": 0-100, "confidence": 0-1, "summary": "风格一致简评"},
    {"key": "factual_support", "raw_score": 0-100, "confidence": 0-1, "summary": "事实支撑简评"}
  ],
  "issues": [
    {
      "id": "1",
      "dimension": "logic_structure|language_grammar|style_consistency|citation_sources|factual_support|figure_quality|ai_signature",
      "issue_type": "unclear_transition|grammar|unsupported_claim|generic_phrasing|...",
      "severity": "high|medium|low",
      "penalty": 1-30,
      "category": "logic|style|grammar|citation|structure|hallucination|figure|code|consistency|other",
      "title": "问题标题（15字内）",
      "detail": "问题说明",
      "quote": "原文中有问题的片段（尽量逐字引用，无则空字符串）",
      "suggestion": "见 action_type 说明",
      "action_type": "replace|delete|insert|revise",
      "paragraph_index": 0,
      "confidence": 0-1
    }
  ]
}

注意：不要输出总分 score；引用来源、图表质量、AI味风险会由程序化 detector 补充，你只在发现明显问题时可输出对应 issue。

action_type 含义（必须准确分类）：
- replace：suggestion 为**可直接替换 quote 的完整改写句/段**（不含「改为」「建议」等说明语）
- delete：删除 quote 指出的片段，suggestion 留空
- insert：在 quote 锚点附近**新增**内容，suggestion 为要插入的完整句子（不是操作说明）
- revise：suggestion 为**给编辑/AI 的操作说明**（如「统一使用我们」「改为不涉及代码」），不可直接当正文替换

要求：
- issues 按严重程度排序，最多 12 条；无重大问题时 issues 可为空数组
- high：事实错误、逻辑矛盾、严重语病、无来源的具体数据/案例、未入库引用；medium：表达、衔接、格式；low：润色级建议
审校维度（逐项扫描）：
- structure：大纲小节是否在正文中有对应节标题；结构是否完整
- logic：论证链、衔接、前后矛盾
- citation / hallucination：无来源断言、未入库引用、具体数据无出处
- grammar：语序与病句
- style / consistency：术语、语气与全书宪法是否一致
- code：代码块是否明显语法错误或与正文描述不符
- figure：图表占位、数据与正文是否一致；数据图是否缺数值
- structure：表格须有表头行与 GFM 分隔行；正文须引用（如「见表1-1」）；序号列须从 1 连续编号

- 重点检查：无来源断言（「研究表明」等）、人名+时间+地点齐全但无出处的「案例」、与【已批准本书文献】不一致的引用
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
        narrative_constitution: str = "",
        approved_citations: list[str] | None = None,
        figure_summaries: list[str] | None = None,
    ) -> dict[str, Any]:
        text = (body or "").strip()
        if not text:
            return {
                "summary": "本章暂无正文，无法审校。",
                "dimensions": {},
                "issues": [],
            }

        if len(text) > 28_000:
            return self._review_long_chapter(
                chapter_title=chapter_title,
                body=text,
                book_title=book_title,
                book_type=book_type,
                citation_style=citation_style,
                user_material=user_material,
                approved_citations=approved_citations,
                figure_summaries=figure_summaries,
                narrative_constitution=narrative_constitution,
            )

        truncated = _preprocess_code_blocks(text[:28_000])
        user_parts = [
            f"书名：{book_title or '未命名'}",
            f"类型：{book_type}",
            f"引用格式要求：{citation_style}",
            f"章节标题：{chapter_title}",
            CHAPTER_PUBLICATION_STANDARDS,
        ]
        if (narrative_constitution or "").strip():
            user_parts.append(f"【全书叙事宪法】\n{narrative_constitution.strip()[:2000]}")
        if user_material.strip():
            user_parts.append(f"作者写作约束（审校时参考）：\n{user_material[:3000]}")
        if approved_citations:
            user_parts.append(
                "【已批准本书文献】\n" + "\n".join(approved_citations[:200])
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
                "dimensions": {},
                "issues": [],
            }

        issues = data.get("issues") or []
        if not isinstance(issues, list):
            issues = []
        normalized: list[dict[str, Any]] = []
        for i, item in enumerate(issues[:MAX_ISSUES]):
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": str(item.get("id") or i + 1),
                    "dimension": str(item.get("dimension") or item.get("category") or "other"),
                    "issue_type": str(item.get("issue_type") or item.get("category") or "review_issue")[:80],
                    "severity": _enum_val(item.get("severity"), ("high", "medium", "low"), "medium"),
                    "penalty": _penalty(item.get("penalty"), item.get("severity")),
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
                            "code",
                            "consistency",
                            "other",
                        ),
                        "other",
                    ),
                    "title": str(item.get("title") or "待改进")[:80],
                    "detail": str(item.get("detail") or item.get("explanation") or "")[:2000],
                    "quote": str(item.get("quote") or "")[:500],
                    "suggestion": str(item.get("suggestion") or item.get("replacement_text") or "")[:2000],
                    "action_type": _enum_val(
                        item.get("action_type") or item.get("action"),
                        ("replace", "delete", "insert", "revise"),
                        _infer_action_type(
                            str(item.get("quote") or ""),
                            str(item.get("suggestion") or ""),
                        ),
                    ),
                    "paragraph_index": _optional_int(item.get("paragraph_index")),
                    "confidence": _confidence(item.get("confidence")),
                }
            )

        from app.services.review_scoring import normalize_agent_dimensions

        raw_dims = data.get("dimensions") or {}
        dimensions = normalize_agent_dimensions(raw_dims)

        return {
            "summary": str(data.get("summary") or "")[:1500],
            "dimensions": {
                k: {
                    "raw_score": dimensions[k]["raw_score"],
                    "summary": dimensions[k]["summary"],
                    "confidence": dimensions[k]["confidence"],
                    "detector": "review_agent",
                    "status": "completed",
                }
                for k in dimensions
            },
            "issues": normalized,
        }

    def _review_long_chapter(
        self,
        *,
        chapter_title: str,
        body: str,
        book_title: str,
        book_type: str,
        citation_style: str,
        user_material: str = "",
        narrative_constitution: str = "",
        approved_citations: list[str] | None = None,
        figure_summaries: list[str] | None = None,
    ) -> dict[str, Any]:
        chunks = _split_review_chunks(body)
        chunk_results: list[tuple[int, dict[str, Any]]] = []
        for idx, chunk in enumerate(chunks, start=1):
            result = self.review_chapter(
                chapter_title=f"{chapter_title}（片段 {idx}/{len(chunks)}）",
                body=chunk,
                book_title=book_title,
                book_type=book_type,
                citation_style=citation_style,
                user_material=user_material,
                approved_citations=approved_citations,
                figure_summaries=figure_summaries,
                narrative_constitution=narrative_constitution,
            )
            chunk_results.append((len(chunk), result))
        return _merge_chunk_reviews(chunk_results, max_issues=MAX_CHUNK_ISSUES)


def _split_review_chunks(text: str, *, limit: int = 16_000) -> list[str]:
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for para in (text or "").split("\n\n"):
        if len(para) > limit:
            if buf:
                chunks.append("\n\n".join(buf))
                buf = []
                size = 0
            for start in range(0, len(para), limit):
                chunks.append(para[start : start + limit])
            continue
        chunk_len = len(para) + (2 if buf else 0)
        if buf and size + chunk_len > limit:
            chunks.append("\n\n".join(buf))
            buf = [para]
            size = len(para)
        else:
            buf.append(para)
            size += chunk_len
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks or [text]


def _preprocess_code_blocks(text: str) -> str:
    """代码块括号粗检，供 LLM 参考。"""
    import re

    notes: list[str] = []
    for m in re.finditer(r"```(\w+)?\n([\s\S]*?)```", text):
        body = m.group(2) or ""
        if body.count("(") != body.count(")"):
            notes.append("某代码块圆括号可能不匹配")
        if body.count("{") != body.count("}"):
            notes.append("某代码块花括号可能不匹配")
    if notes:
        return text + "\n\n【程序化代码块提示】" + "；".join(dict.fromkeys(notes))
    return text


def _merge_chunk_reviews(chunk_results: list[tuple[int, dict[str, Any]]], *, max_issues: int = MAX_CHUNK_ISSUES) -> dict[str, Any]:
    total_len = sum(max(1, length) for length, _ in chunk_results) or 1
    dim_acc: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    seen: set[str] = set()
    summaries: list[str] = []
    for length, result in chunk_results:
        weight = max(1, length) / total_len
        summary = str(result.get("summary") or "").strip()
        if summary:
            summaries.append(summary[:240])
        for key, dim in (result.get("dimensions") or {}).items():
            if not isinstance(dim, dict):
                continue
            acc = dim_acc.setdefault(
                str(key),
                {"raw_score": 0.0, "confidence": 0.0, "summary": [], "status": "completed"},
            )
            acc["raw_score"] += float(dim.get("raw_score", 70) or 70) * weight
            acc["confidence"] += float(dim.get("confidence", 0.7) or 0.7) * weight
            if dim.get("summary"):
                acc["summary"].append(str(dim.get("summary"))[:180])
            if str(dim.get("status") or "completed") != "completed":
                acc["status"] = "partial"
        for issue in result.get("issues") or []:
            if not isinstance(issue, dict):
                continue
            key = "|".join(
                [
                    str(issue.get("dimension") or ""),
                    str(issue.get("issue_type") or ""),
                    str(issue.get("quote") or "")[:120],
                    str(issue.get("title") or "")[:80],
                ]
            )
            if key in seen:
                continue
            seen.add(key)
            issues.append(issue)
    dimensions = {
        key: {
            "raw_score": int(round(acc["raw_score"])),
            "summary": "；".join(acc["summary"][:3]),
            "confidence": round(float(acc["confidence"]), 3),
            "detector": "review_agent:chunked",
            "status": acc["status"],
        }
        for key, acc in dim_acc.items()
    }
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: (severity_rank.get(str(i.get("severity")), 1), -int(i.get("penalty") or 0)))
    return {
        "summary": "长章分块审校完成：" + "；".join(summaries[:4]),
        "dimensions": dimensions,
        "issues": issues[:max_issues],
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


def _penalty(raw: Any, severity: Any) -> int:
    try:
        return max(0, min(30, int(raw)))
    except (TypeError, ValueError):
        return {"high": 10, "medium": 6, "low": 3}.get(str(severity or "").lower(), 6)


def _optional_int(raw: Any) -> int | None:
    try:
        if raw is None or raw == "":
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def _confidence(raw: Any) -> float:
    try:
        val = float(raw)
    except (TypeError, ValueError):
        val = 0.7
    return max(0.0, min(1.0, round(val, 3)))
