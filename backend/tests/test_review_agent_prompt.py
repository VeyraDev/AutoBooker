"""Tests for the runtime review prompt registry and agent field contract."""

from __future__ import annotations

import json
from typing import Any

from app.agents.review_agent import REVIEW_SYSTEM, ReviewAgent
from app.prompts.review_quality import build_chapter_review_system_prompt, get_review_prompt_asset
from app.services.review_scoring import standardize_issue


def test_chapter_review_system_prompt_is_composed_from_registry():
    asset = get_review_prompt_asset("chapter_llm_review_system")
    prompt = build_chapter_review_system_prompt()

    assert asset.prompt == prompt
    assert REVIEW_SYSTEM == prompt
    assert "审校器通用系统提示词" in prompt
    assert "章节 LLM 综合审校器提示词" in prompt
    assert "参考文献真实性审校器提示词" in prompt
    assert "AI 文本风险检测提示词" in prompt
    assert "一键修复路由器提示词" in prompt
    assert "不能生成、补造" in prompt
    assert "fix_capability" in prompt


def test_review_agent_preserves_evidence_and_fixability_fields():
    class FakeClient:
        def __init__(self) -> None:
            self.messages: list[dict[str, str]] = []

        def chat_completion(self, messages: list[dict[str, str]], **_: Any) -> str:
            self.messages = messages
            return json.dumps(
                {
                    "summary": "发现一处待核验来源问题。",
                    "dimensions": [
                        {
                            "key": "factual_support",
                            "raw_score": 68,
                            "confidence": 0.81,
                            "summary": "部分数据缺少来源。",
                        }
                    ],
                    "issues": [
                        {
                            "id": "src_001",
                            "dimension": "citation_sources",
                            "category": "citation",
                            "issue_type": "missing_citation",
                            "severity": "needs_verification",
                            "tier": "needs_verification",
                            "title": "具体比例缺少来源",
                            "detail": "原文使用了具体比例，但未看到可核验来源。",
                            "why_it_matters": "具体比例会影响读者对论证可信度的判断。",
                            "location": {
                                "paragraph_index": 2,
                                "char_start": 5,
                                "char_end": 24,
                                "quote": "研究表明，60%的读者会优先关注案例。",
                            },
                            "evidence": ["包含“研究表明”和“60%”，但没有引用标记。"],
                            "basis_refs": ["原文章节第3段"],
                            "action_type": "choose",
                            "action_options": [
                                {
                                    "id": "verify_source",
                                    "label": "补充来源",
                                    "description": "上传或绑定含摘要的文献来源",
                                    "action_type": "manual",
                                }
                            ],
                            "fix_capability": "choice_then_apply",
                            "product_dimension": "evidence_citation",
                            "verification_status": "needs_verification",
                            "confidence": 0.88,
                        }
                    ],
                },
                ensure_ascii=False,
            )

    agent = ReviewAgent(model="test-model")
    fake = FakeClient()
    agent._client = fake  # type: ignore[attr-defined]

    result = agent.review_chapter(
        chapter_title="来源意识",
        body="第一段。\n\n第二段。\n\n研究表明，60%的读者会优先关注案例。",
        book_title="审校测试书",
        book_type="学术专著",
        citation_style="GB/T 7714",
    )

    assert fake.messages[0]["role"] == "system"
    assert "章节 LLM 综合审校器提示词" in fake.messages[0]["content"]

    issue = result["issues"][0]
    assert issue["severity"] == "needs_verification"
    assert issue["action_type"] == "choose"
    assert issue["quote"] == "研究表明，60%的读者会优先关注案例。"
    assert issue["paragraph_index"] == 2
    assert issue["char_start"] == 5
    assert issue["fix_capability"] == "choice_then_apply"
    assert issue["product_dimension"] == "evidence_citation"
    assert issue["quality_evidence"]["evidence"] == ["包含“研究表明”和“60%”，但没有引用标记。"]
    assert issue["quality_evidence"]["basis_refs"] == ["原文章节第3段"]

    standardized = standardize_issue(issue)
    assert standardized["severity"] == "needs_verification"
    assert standardized["action_type"] == "choose"
    assert standardized["fix_capability"] == "choice_then_apply"
    assert standardized["product_dimension"] == "evidence_citation"
    assert standardized["basis_refs"] == ["原文章节第3段"]
    assert standardized["evidence"] == ["包含“研究表明”和“60%”，但没有引用标记。"]
