"""Quality-gated text deduplication service."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.llm.client import LLMClient
from app.services.ai_detect import get_ai_detect_provider, result_to_dict
from app.services.dedupe_verify import (
    assess_similarity_warnings,
    extract_facts,
    similarity_score,
    split_by_headings,
    verify_facts_preserved,
)
from app.services.quality import QualityStatus

_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_TABLE_RE = re.compile(r"(?m)^\|.+\|\s*\n^\|(?:\s*:?-{3,}:?\s*\|)+(?:\n^\|.*\|\s*)*")
_CITATION_RE = re.compile(r"\[[0-9]{1,3}\]|\([A-Za-z\u4e00-\u9fff][^()]{0,40},\s*(?:\d{4}|n\.d\.)\)")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?|\d{4}年")
_FIG_TABLE_REF_RE = re.compile(r"[图表]\s*\d+(?:[-－—]\d+)?")
_TERM_RE = re.compile(r"[A-Z][A-Za-z0-9_+-]{2,}|《[^》]{2,40}》|“[^”]{2,40}”|「[^」]{2,40}」")
_HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+)$")

_MAX_REWRITE_ROUNDS = 2
_RISK_ROLLBACK_DELTA = 0.15


@dataclass
class DedupeResult:
    text: str
    original_text: str
    report: dict[str, Any]


class DedupeService:
    chunk_chars = 7000

    def dedupe_text(
        self,
        text: str,
        *,
        client: LLMClient,
        chat_model: str,
        context: str = "",
        glossary_terms: list[str] | None = None,
    ) -> DedupeResult:
        return self._run(
            text,
            client=client,
            chat_model=chat_model,
            context_summary=context,
            whole_chapter=False,
            glossary_terms=glossary_terms,
        )

    def dedupe_markdown(
        self,
        markdown: str,
        *,
        client: LLMClient,
        chat_model: str,
        context_summary: str = "",
        glossary_terms: list[str] | None = None,
    ) -> DedupeResult:
        return self._run(
            markdown,
            client=client,
            chat_model=chat_model,
            context_summary=context_summary,
            whole_chapter=True,
            glossary_terms=glossary_terms,
        )

    def _run(
        self,
        text: str,
        *,
        client: LLMClient,
        chat_model: str,
        context_summary: str,
        whole_chapter: bool,
        glossary_terms: list[str] | None = None,
    ) -> DedupeResult:
        original = (text or "").strip()
        before_risk, before_raw, detect_warnings = self._detect_risk(original)
        facts = extract_facts(client, chat_model, original)
        protected = _extract_protected(original, extra_terms=glossary_terms)
        masked, replacements = _mask_protected_blocks(original)
        chunks = split_by_headings(masked, fallback_limit=self.chunk_chars) if whole_chapter else _split_chunks(masked, self.chunk_chars)
        rewritten_chunks: list[str] = []
        chunk_reports: list[dict[str, Any]] = []
        running_summary = (context_summary or "")[:1600]
        all_passed = True

        for idx, chunk in enumerate(chunks):
            chunk_original_risk, _, _ = self._detect_risk(chunk)
            rewritten, chunk_report = self._rewrite_with_retry(
                client,
                chat_model,
                chunk,
                protected=protected,
                context_summary=running_summary,
                chunk_index=idx + 1,
                chunk_count=len(chunks),
                whole_chapter=whole_chapter,
                facts=facts,
                before_risk=chunk_original_risk,
            )
            chunk_reports.append(chunk_report)
            if chunk_report.get("status") != QualityStatus.passed.value:
                all_passed = False
            rewritten_chunks.append(rewritten.strip())
            running_summary = _rolling_summary(running_summary, rewritten)

        rewritten_text = "\n\n".join(x for x in rewritten_chunks if x)
        rewritten_text = _restore_protected_blocks(rewritten_text, replacements)

        if whole_chapter and len(chunks) > 1 and len(rewritten_text) <= 24000 and all_passed:
            unified = self._style_unify_pass(client, chat_model, rewritten_text, protected=protected)
            rewritten_text = _restore_protected_blocks(unified.strip(), replacements)

        after_risk, after_raw, after_warnings = self._detect_risk(rewritten_text)
        warnings = detect_warnings + after_warnings
        validation = _validate_preservation(original, rewritten_text, protected)
        warnings.extend(validation["warnings"])

        sim = similarity_score(original, rewritten_text)
        warnings.extend(assess_similarity_warnings(sim))
        missing_facts = verify_facts_preserved(facts, rewritten_text)
        if missing_facts:
            validation["protected_tokens_changed"] = list(validation.get("protected_tokens_changed") or []) + [
                f"fact:{f[:40]}" for f in missing_facts[:8]
            ]

        chunk_failed = any(
            cr.get("status") == QualityStatus.failed.value for cr in chunk_reports
        )
        if chunk_failed and not validation["protected_tokens_changed"]:
            validation["protected_tokens_changed"] = [
                str(cr.get("last_failure") or "chunk_rewrite_failed")
                for cr in chunk_reports
                if cr.get("status") == QualityStatus.failed.value
            ]
        status = QualityStatus.passed.value
        if validation["protected_tokens_changed"] or chunk_failed:
            status = QualityStatus.failed.value
        elif warnings or (after_risk is not None and before_risk is not None and after_risk > before_risk):
            status = QualityStatus.warning.value

        report = {
            "status": status,
            "before_ai_risk": before_risk,
            "after_ai_risk": after_risk,
            "risk_delta": None if before_risk is None or after_risk is None else round(after_risk - before_risk, 3),
            "similarity_score": sim,
            "meaning_preserved": validation["meaning_preserved"] and not missing_facts,
            "structure_preserved": validation["structure_preserved"],
            "protected_tokens_changed": validation["protected_tokens_changed"],
            "facts_extracted": facts[:20],
            "facts_missing": missing_facts[:12],
            "warnings": list(dict.fromkeys(warnings)),
            "chunk_reports": chunk_reports,
            "protected_summary": {
                "numbers": len(protected["numbers"]),
                "citations": len(protected["citations"]),
                "terms": len(protected["terms"]),
                "code_blocks": len(protected["code_blocks"]),
                "tables": len(protected["tables"]),
                "figure_table_refs": len(protected["figure_table_refs"]),
            },
            "detector": {
                "before": before_raw,
                "after": after_raw,
            },
        }
        if status == QualityStatus.failed.value:
            return DedupeResult(text=original, original_text=original, report=report)
        return DedupeResult(text=rewritten_text, original_text=original, report=report)

    def _rewrite_with_retry(
        self,
        client: LLMClient,
        chat_model: str,
        chunk: str,
        *,
        protected: dict[str, list[str]],
        context_summary: str,
        chunk_index: int,
        chunk_count: int,
        whole_chapter: bool,
        facts: list[str],
        before_risk: float | None,
    ) -> tuple[str, dict[str, Any]]:
        failure_reason = ""
        current = chunk
        report: dict[str, Any] = {"chunk_index": chunk_index, "rounds": 0, "status": QualityStatus.passed.value}

        for round_idx in range(1, _MAX_REWRITE_ROUNDS + 1):
            report["rounds"] = round_idx
            rewritten = self._rewrite_chunk(
                client,
                chat_model,
                current,
                protected=protected,
                context_summary=context_summary,
                chunk_index=chunk_index,
                chunk_count=chunk_count,
                whole_chapter=whole_chapter,
                failure_reason=failure_reason,
            )
            validation = _validate_preservation(chunk, rewritten, protected)
            missing_facts = verify_facts_preserved(facts, rewritten)
            after_risk, _, _ = self._detect_risk(rewritten)
            risk_up = (
                before_risk is not None
                and after_risk is not None
                and after_risk - before_risk > _RISK_ROLLBACK_DELTA
            )
            if validation["protected_tokens_changed"] or missing_facts or risk_up:
                failure_reason = (
                    "保护元素丢失"
                    if validation["protected_tokens_changed"]
                    else "事实未保留"
                    if missing_facts
                    else "AI风险上升"
                )
                report["last_failure"] = failure_reason
                if round_idx >= _MAX_REWRITE_ROUNDS:
                    report["status"] = QualityStatus.failed.value
                    return chunk, report
                current = chunk
                continue
            report["status"] = QualityStatus.passed.value
            return rewritten, report

        report["status"] = QualityStatus.failed.value
        return chunk, report

    def _rewrite_chunk(
        self,
        client: LLMClient,
        chat_model: str,
        chunk: str,
        *,
        protected: dict[str, list[str]],
        context_summary: str,
        chunk_index: int,
        chunk_count: int,
        whole_chapter: bool,
        failure_reason: str = "",
    ) -> str:
        system = "你是专业中文编辑，只输出改写后的正文，不要加引号、标题或前言。"
        constraints = _protected_prompt(protected)
        scope = "整章分块" if whole_chapter else "选区"
        retry = f"\n上次失败原因：{failure_reason}。务必保留所有事实与保护元素。\n" if failure_reason else ""
        user = (
            "请对文本做降重改写：保留原意、事实、数字、引用、术语、标题层级、Markdown 表格、代码块和图表编号；"
            "通过调整句式、衔接和词序降低模板化与雷同表达。不要添加新观点，不要删减关键信息。\n\n"
            f"处理范围：{scope}，第 {chunk_index}/{chunk_count} 块。\n"
            f"上下文摘要：{context_summary or '无'}\n"
            f"{constraints}\n"
            f"{retry}\n"
            f"---\n{chunk.strip()}"
        )
        return client.chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=chat_model,
            max_tokens=8192,
            temperature=0.55,
        )

    def _style_unify_pass(
        self,
        client: LLMClient,
        chat_model: str,
        text: str,
        *,
        protected: dict[str, list[str]],
    ) -> str:
        system = "你是专业中文编辑，只输出处理后的正文。"
        user = (
            "请只做全章语气与术语统一，不要继续大幅改写。必须保留所有数字、引用、Markdown 结构、表格、代码块和图表编号。\n"
            f"{_protected_prompt(protected)}\n\n---\n{text}"
        )
        return client.chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=chat_model,
            max_tokens=8192,
            temperature=0.35,
        )

    def _detect_risk(self, text: str) -> tuple[float | None, dict[str, Any] | None, list[str]]:
        if not text.strip():
            return 0.0, None, []
        try:
            result = get_ai_detect_provider().detect(text)
            return float(result.overall_score), result_to_dict(result), []
        except Exception as exc:
            return None, None, [f"ai_detect_unavailable:{type(exc).__name__}"]


def _mask_protected_blocks(text: str) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        key = f"@@PROTECTED_BLOCK_{len(replacements)}@@"
        replacements[key] = match.group(0)
        return key

    masked = _CODE_FENCE_RE.sub(repl, text)
    masked = _TABLE_RE.sub(repl, masked)
    masked = _INLINE_CODE_RE.sub(repl, masked)
    return masked, replacements


def _restore_protected_blocks(text: str, replacements: dict[str, str]) -> str:
    out = text
    for key, value in replacements.items():
        out = out.replace(key, value)
    return out


def _extract_protected(text: str, *, extra_terms: list[str] | None = None) -> dict[str, list[str]]:
    terms = _unique(_TERM_RE.findall(text or ""))[:80]
    if extra_terms:
        terms = _unique(terms + [t for t in extra_terms if t])[:100]
    return {
        "headings": [m.group(1) for m in _HEADING_RE.finditer(text or "")],
        "code_blocks": _CODE_FENCE_RE.findall(text or ""),
        "tables": _TABLE_RE.findall(text or ""),
        "citations": _unique(_CITATION_RE.findall(text or "")),
        "numbers": _unique(_NUMBER_RE.findall(text or "")),
        "terms": terms,
        "figure_table_refs": _unique(_FIG_TABLE_REF_RE.findall(text or "")),
    }


def _validate_preservation(original: str, rewritten: str, protected: dict[str, list[str]]) -> dict[str, Any]:
    warnings: list[str] = []
    changed: list[str] = []
    for key in ("citations", "numbers", "figure_table_refs", "terms"):
        missing = [tok for tok in protected[key] if tok and tok not in rewritten]
        if missing:
            changed.extend(f"{key}:{tok}" for tok in missing[:12])
    if protected["headings"] != [m.group(1) for m in _HEADING_RE.finditer(rewritten or "")]:
        warnings.append("heading_hierarchy_changed")
    if len(protected["code_blocks"]) != len(_CODE_FENCE_RE.findall(rewritten or "")):
        changed.append("code_block_count_changed")
    if len(protected["tables"]) != len(_TABLE_RE.findall(rewritten or "")):
        changed.append("markdown_table_count_changed")
    ratio = len(rewritten) / max(1, len(original))
    if ratio < 0.55 or ratio > 1.9:
        warnings.append("length_ratio_out_of_range")
    return {
        "meaning_preserved": not changed and 0.55 <= ratio <= 1.9,
        "structure_preserved": "heading_hierarchy_changed" not in warnings and "code_block_count_changed" not in changed and "markdown_table_count_changed" not in changed,
        "protected_tokens_changed": changed,
        "warnings": warnings,
    }


def _split_chunks(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for para in re.split(r"\n\n+", text):
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


def _protected_prompt(protected: dict[str, list[str]]) -> str:
    tokens = []
    for key in ("citations", "numbers", "figure_table_refs", "terms"):
        values = protected.get(key) or []
        if values:
            tokens.append(f"{key}: " + "、".join(values[:40]))
    return "必须逐字保留的保护元素：\n" + "\n".join(tokens) if tokens else "无额外保护元素。"


def _rolling_summary(previous: str, rewritten: str) -> str:
    text = (previous + "\n" + rewritten[:800]).strip()
    return text[-1600:]


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out
