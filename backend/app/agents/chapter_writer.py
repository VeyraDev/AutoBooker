"""Stream chapter body via configured LLM provider."""

from __future__ import annotations

import re
from typing import Any, AsyncIterator

from app.llm.client import AsyncLLMClient, LLMClient
from app.prompts.chapter_writer import build_writer_system_prompt
from app.services.chapter_markdown_assembler import compute_section_word_budgets

_TRUNCATION_END_RE = re.compile(r"[。！？…」」\)\]】\.\!\?]$")
_CONTINUATION_USER = (
    "上文因输出长度限制在中途截断。请从断点处紧接着写完本章剩余正文，"
    "不要重复已有段落，不要加任何说明或前言。"
)


def chapter_output_looks_truncated(text: str, target_words: int) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    actual = len(t.replace("\n", "").replace(" ", ""))
    if actual < int(max(target_words, 800) * 0.72):
        return True
    return _TRUNCATION_END_RE.search(t) is None


class ChapterWriterAgent:
    def __init__(self) -> None:
        self._client = AsyncLLMClient()

    def _build_messages(
        self,
        chapter: dict[str, Any],
        book_memory: dict[str, Any],
        reference_snippets: list[str],
        *,
        citation_blocks: list[str] | None = None,
        temperature: float | None = None,
    ) -> tuple[list[dict[str, str]], float]:
        constitution = (book_memory.get("narrative_constitution") or "").strip() or (
            "（未生成叙事宪法，请按体裁常识写作。）"
        )
        cites = citation_blocks or []
        policy = book_memory.get("citation_policy") or ""
        sections = chapter.get("sections") or []
        system = build_writer_system_prompt(
            outline_sections=sections if isinstance(sections, list) else [],
            book_type=book_memory["book_type"],
            narrative_constitution=constitution,
            style_examples=book_memory.get("style_examples", ""),
            chapter_index=chapter.get("chapter_index", 1),
            total_chapters=chapter.get("total_chapters", 1),
            chapter_title=chapter.get("title", ""),
            prev_chapter_hook=book_memory.get("prev_chapter_hook", "无"),
            style_voice_block=book_memory.get("style_voice_block", ""),
            topic_tags_line=book_memory.get("topic_tags_line", "（未选标签）"),
            user_material=book_memory.get("user_material", "（无）"),
            style_guide=book_memory.get("style_guide", "流畅自然，逻辑清晰"),
            citation_style=book_memory.get("citation_style", "无"),
            term_glossary=str(book_memory.get("terms", {})),
            target_words=chapter.get("estimated_words", 3000),
            citation_policy=policy,
        )
        user_msg = self._build_user_message(chapter, reference_snippets, cites)
        temp = temperature if temperature is not None else float(book_memory.get("writer_temperature", 0.75))
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]
        return messages, temp

    async def stream(
        self,
        chapter: dict[str, Any],
        book_memory: dict[str, Any],
        reference_snippets: list[str],
        *,
        citation_blocks: list[str] | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        messages, temp = self._build_messages(
            chapter,
            book_memory,
            reference_snippets,
            citation_blocks=citation_blocks,
            temperature=temperature,
        )
        estimated_words = int(chapter.get("estimated_words") or 3000)
        max_tokens = LLMClient.completion_budget_for_chinese_words(estimated_words, model)
        conv: list[dict[str, str]] = list(messages)
        combined = ""

        for round_idx in range(2):
            round_text = ""
            async for token in self._client.stream_chat(
                conv,
                model=model,
                max_tokens=max_tokens,
                temperature=temp,
            ):
                round_text += token
                yield token
            combined += round_text
            if round_idx == 0 and chapter_output_looks_truncated(combined, estimated_words):
                conv = [
                    *conv,
                    {"role": "assistant", "content": combined},
                    {"role": "user", "content": _CONTINUATION_USER},
                ]
                max_tokens = LLMClient.completion_budget_for_chinese_words(
                    max(estimated_words, len(combined.replace("\n", "").replace(" ", ""))),
                    model,
                )
                continue
            break

    def _build_user_message(
        self,
        chapter: dict[str, Any],
        snippets: list[str],
        citation_blocks: list[str],
    ) -> str:
        sections = chapter.get("sections") or []
        total_words = int(chapter.get("estimated_words") or 3000)
        budgets = compute_section_word_budgets(sections, total_words)

        parts = [
            f"本章摘要：{chapter.get('summary', '')}",
            f"核心论点：{'; '.join(chapter.get('key_points', []))}",
            f"本章总字数约 {total_words} 字，共 {len(sections) or 1} 节。",
        ]
        if sections:
            parts.append("【各节写作要求（按顺序输出整章 Markdown，每节先写标题行）】")
            for i, sec in enumerate(sections):
                title = str(sec.get("title") or f"第{i + 1}节")
                summary = str(sec.get("summary") or "")
                budget = budgets[i] if i < len(budgets) else total_words // max(len(sections), 1)
                parts.append(f"- 第 {i + 1} 节：{title}")
                parts.append(f"  摘要：{summary}")
                parts.append(f"  目标字数：约 {budget} 字（允许 ±15%）")
        else:
            parts.append("【单节】直接输出本章正文段落，不要写标题行。")

        if citation_blocks:
            parts.append("【已批准引用库】（正文引用只能来自以下条目）")
            parts.extend([f"- {b}" for b in citation_blocks])
        if snippets:
            parts.append("【上传资料检索片段】")
            parts.extend([f"- {s}" for s in snippets])
        parts.append("请一次性输出整章 Markdown 正文，严格遵守系统提示中的标题层级与节次顺序。")
        return "\n".join(parts)
