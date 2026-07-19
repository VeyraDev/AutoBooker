"""Tests for the runtime review prompt registry and agent field contract."""

from __future__ import annotations

import json
from typing import Any

from app.agents.review_agent import REVIEW_SYSTEM, ReviewAgent
from app.prompts.review_quality import (
    build_ai_rewrite_prompt,
    build_chapter_review_system_prompt,
    build_review_prompt,
    get_review_prompt_asset,
)
from app.services.review_scoring import standardize_issue


def test_review_prompts_are_selected_by_task_instead_of_recombined():
    asset = get_review_prompt_asset("chapter_llm_review_system")
    prompt = build_chapter_review_system_prompt()

    assert asset.prompt == prompt
    assert REVIEW_SYSTEM == prompt
    assert "当前任务：内容与论证审校" in prompt
    assert "当前任务：资料、事实与参考文献审校" not in prompt
    assert "当前任务：编校语言与 AI 表达风险审校" not in prompt
    assert "preview_apply 只允许" not in prompt

    reference_prompt = build_review_prompt("reference_evidence", "academic_monograph")
    language_prompt = build_review_prompt("language_ai", "biography")
    assert "当前任务：资料、事实与参考文献审校" in reference_prompt
    assert "学术专著补丁" in reference_prompt
    assert "人物传记补丁" not in reference_prompt
    assert "当前任务：编校语言与 AI 表达风险审校" in language_prompt
    assert "人物传记补丁" in language_prompt
    assert "本章生成时实际使用的资料" not in language_prompt
    assert "只输出可直接替换原文" not in language_prompt
    assert "只输出可直接替换原文" in build_ai_rewrite_prompt("biography")


def test_review_agent_preserves_evidence_and_fixability_fields():
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[list[dict[str, str]]] = []

        def chat_completion(self, messages: list[dict[str, str]], **_: Any) -> str:
            self.calls.append(messages)
            if "当前任务：资料、事实与参考文献审校" not in messages[0]["content"]:
                return json.dumps({"findings": []}, ensure_ascii=False)
            return json.dumps(
                {
                    "findings": [
                        {
                            "id": "src_001",
                            "dimension": "citation_sources",
                            "category": "citation",
                            "issue_type": "missing_citation",
                            "proposed_severity": "needs_verification",
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
        narrative_constitution="NARRATIVE_ONLY_TOKEN",
        approved_citations=["BOUND_REFERENCE_ONLY_TOKEN"],
        review_instruction="CUSTOM_REVIEW_ONLY_TOKEN",
        user_material=(
            "【写作要求】\nWRITING_REQUIREMENT_ONLY_TOKEN\n\n"
            "【本阶段检索到的资料依据】\nSOURCE_EVIDENCE_ONLY_TOKEN"
        ),
    )

    assert len(fake.calls) == 3
    system_prompts = [call[0]["content"] for call in fake.calls]
    assert any("当前任务：内容与论证审校" in prompt for prompt in system_prompts)
    assert any("当前任务：资料、事实与参考文献审校" in prompt for prompt in system_prompts)
    assert any("当前任务：编校语言与 AI 表达风险审校" in prompt for prompt in system_prompts)
    reference_call = next(call for call in fake.calls if "资料、事实与参考文献" in call[0]["content"])
    content_call = next(call for call in fake.calls if "内容与论证审校" in call[0]["content"])
    language_call = next(call for call in fake.calls if "编校语言与 AI 表达风险" in call[0]["content"])
    assert "BOUND_REFERENCE_ONLY_TOKEN" in reference_call[1]["content"]
    assert "BOUND_REFERENCE_ONLY_TOKEN" not in content_call[1]["content"]
    assert "BOUND_REFERENCE_ONLY_TOKEN" not in language_call[1]["content"]
    assert "NARRATIVE_ONLY_TOKEN" in content_call[1]["content"]
    assert "NARRATIVE_ONLY_TOKEN" not in language_call[1]["content"]
    assert "WRITING_REQUIREMENT_ONLY_TOKEN" in content_call[1]["content"]
    assert "WRITING_REQUIREMENT_ONLY_TOKEN" in language_call[1]["content"]
    assert "WRITING_REQUIREMENT_ONLY_TOKEN" not in reference_call[1]["content"]
    assert "SOURCE_EVIDENCE_ONLY_TOKEN" in reference_call[1]["content"]
    assert "SOURCE_EVIDENCE_ONLY_TOKEN" not in content_call[1]["content"]
    assert "SOURCE_EVIDENCE_ONLY_TOKEN" not in language_call[1]["content"]
    assert all("CUSTOM_REVIEW_ONLY_TOKEN" in call[1]["content"] for call in fake.calls)

    issue = result["issues"][0]
    assert issue["severity"] == "needs_verification"
    assert issue["action_type"] == "choose"
    assert issue["quote"] == "研究表明，60%的读者会优先关注案例。"
    assert issue["paragraph_index"] == 2
    assert issue["char_start"] == 5
    assert issue["fix_capability"] == "choice_then_apply"
    assert issue["quality_evidence"]["evidence"] == ["包含“研究表明”和“60%”，但没有引用标记。"]
    assert issue["quality_evidence"]["basis_refs"] == ["原文章节第3段"]

    standardized = standardize_issue(issue)
    assert standardized["severity"] == "needs_verification"
    assert standardized["action_type"] == "choose"
    assert standardized["fix_capability"] == "choice_then_apply"
    assert standardized["product_dimension"] == "evidence_citation"
    assert standardized["basis_refs"] == ["原文章节第3段"]
    assert standardized["evidence"] == ["包含“研究表明”和“60%”，但没有引用标记。"]
