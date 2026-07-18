"""Deterministic review detectors for the review refactor.

These reviewers implement the first phase of the evidence-first review plan.
They intentionally avoid LLM calls and emit findings with the same metadata
contract used by the workspace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.models.book import Book
from app.models.chapter import Chapter
from app.services.citation_service import is_bibliography_chapter
from app.services.review.data_evidence_policy import default_data_action_options
from app.services.review.title_benchmarks import title_benchmark_for_style, title_limits_from_benchmark
from app.services.review_anchor import parse_paragraphs
from app.services.tiptap_convert import chapter_content_to_markdown


@dataclass(frozen=True)
class QualityReviewResult:
    detector_dimensions: dict[str, dict[str, Any]]
    issues: list[dict[str, Any]]


_MARKETING_WORDS = ("终极", "必看", "全网最全", "秒懂", "暴富", "秘籍", "颠覆", "逆袭")
_ABSTRACT_TITLE_WORDS = ("未来", "变革", "新纪元", "重塑", "范式", "生态")
_THEORY_SUFFIXES = ("理论", "模型", "框架", "机制", "范式")
_GENERIC_AI_PHRASES = (
    "综上所述",
    "总的来说",
    "值得注意的是",
    "在这个过程中",
    "从某种意义上说",
    "既是机遇也是挑战",
    "全面、系统、深入",
    "不断探索",
)
_UNSOURCED_MARKERS = ("研究表明", "数据显示", "调查发现", "业界普遍认为", "大量实践证明")
_CITATION_MARKER_RE = re.compile(r"(\[[0-9，,\-\s]+\]|（[^）]{0,40}\d{4}[^）]{0,40}）|doi|DOI|https?://)")
_PERCENT_RE = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?\s?%")
_REFERENCE_LINE_RE = re.compile(r"^\s*\[\d+\].{8,}?(?:\[J\]|\[M\]|\[D\]|\[C\]|DOI|doi)", re.MULTILINE)
_FIGURE_RE = re.compile(r"图\s*(\d+)\s*[-–.]\s*(\d+)")
_TABLE_RE = re.compile(r"表\s*(\d+)\s*[-–.]\s*(\d+)")


def run_book_quality_review(
    book: Book,
    chapters: list[Chapter],
    context_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return book/workspace-level findings for deterministic quality checks."""
    snap = context_snapshot if isinstance(context_snapshot, dict) else {}
    book_style = _book_style(book)
    findings: list[dict[str, Any]] = []
    findings.extend(_review_title(book.title or "", book_style=book_style, level="book", context=snap))
    findings.extend(_review_citation_metadata(snap))
    for ch in chapters:
        if is_bibliography_chapter(ch):
            continue
        md = _chapter_markdown(ch)
        findings.extend(_review_title(ch.title or "", book_style=book_style, level="chapter", chapter_index=ch.index, context=snap))
        findings.extend(_chapter_findings(ch, md, book_style=book_style, context=snap, book_level=True))
    return findings[:80]


def _review_citation_metadata(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = context.get("citations") if isinstance(context, dict) else []
    if not isinstance(rows, list):
        return []
    findings: list[dict[str, Any]] = []
    for row in rows[:200]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        metadata_status = str(row.get("metadata_status") or "").strip()
        verification_status = str(row.get("verification_status") or "").strip()
        source = str(row.get("source") or "").strip()
        doc_type = str(row.get("document_type") or "").strip().lower()
        has_abstract = bool(row.get("has_abstract"))
        missing_fields = [str(x) for x in (row.get("missing_fields") or []) if str(x).strip()]
        recommended_search_query = str(row.get("recommended_search_query") or "").strip()
        missing_core = not title or not (row.get("authors") or []) or not (row.get("year") or row.get("doi") or row.get("url"))
        academic_type = doc_type in {"journal_article", "dissertation", "conference_paper", "j", "d", "c"}
        missing_abstract = source == "uploaded_file" and academic_type and not has_abstract
        if verification_status == "mismatch":
            findings.append(
                _finding(
                    category="reference_authenticity",
                    dimension="citation_sources",
                    issue_type="reference_metadata_mismatch",
                    severity="high",
                    title="参考文献核验不一致",
                    detail=f"文献《{title or '未命名文献'}》与外部核验结果存在不一致，建议人工确认题名、作者、年份或 DOI。",
                    quote=title or str(row.get("doi") or row.get("url") or ""),
                    detector="reference_authenticity_reviewer",
                    product_dimension="evidence_citation",
                    fix_capability="manual_only",
                    verification_status="mismatch",
                    why="文献元数据不一致会影响正文引用可信度，且可能造成张冠李戴或错误归因，不能自动修复。",
                    action_options=[
                        _action("verify_external", "人工核验", recommended_search_query or "按题名、作者、年份重新检索", "manual"),
                        _action("replace_reference", "替换文献", "删除或替换为核验一致的来源", "manual"),
                    ],
                    action="revise",
                    confidence=0.9,
                )
            )
            continue
        if (
            metadata_status == "complete"
            and (not verification_status or verification_status in {"verified", "probable", "user_uploaded_only"})
            and not missing_core
            and not missing_abstract
        ):
            continue
        if missing_abstract:
            reason = "缺少摘要"
        elif missing_fields:
            reason = "缺少字段：" + "、".join(missing_fields[:5])
        elif verification_status == "unreachable":
            reason = "外部检索暂不可达"
        elif verification_status == "needs_verification":
            reason = "尚未完成外部核验"
        else:
            reason = "题名、作者、年份、DOI/URL 等关键字段不完整"
        findings.append(
            _finding(
                category="reference_authenticity",
                dimension="citation_sources",
                issue_type="reference_metadata_incomplete",
                severity="needs_verification",
                title="参考文献元数据不完整",
                detail=f"文献《{title or '未命名文献'}》{reason}，用于核心论证前建议补齐可核验元数据。",
                quote=title or str(row.get("doi") or row.get("url") or ""),
                detector="reference_authenticity_reviewer",
                product_dimension="evidence_citation",
                fix_capability="choice_then_apply",
                verification_status="needs_verification",
                why="参考文献缺少摘要或关键元数据时，系统难以判断其与章节论证的真实相关度，也会降低审校依据强度。",
                action_options=[
                    _action(
                        "upload_cnki_abstract",
                        "补充含摘要导出",
                        "从知网或原始数据库导出含摘要、关键词、卷期页、DOI 的格式后上传",
                        "manual",
                    ),
                    _action("complete_metadata", "补齐元数据", "补充作者、来源、年份、卷期页或 DOI/URL", "manual"),
                    _action(
                        "search_external",
                        "外部检索核验",
                        recommended_search_query or "用题名、作者、年份在公开数据库检索",
                        "manual",
                    ),
                    _action("mark_weak_source", "标为弱依据", "暂不作为核心论证强依据使用", "choose"),
                ],
                action="choose",
                confidence=0.86,
            )
        )
        if len(findings) >= 20:
            break
    return findings


def run_chapter_quality_review(
    book: Book,
    chapter: Chapter,
    markdown: str,
    context_snapshot: dict[str, Any] | None = None,
) -> QualityReviewResult:
    """Return chapter issue candidates and detector dimension metadata."""
    snap = context_snapshot if isinstance(context_snapshot, dict) else {}
    book_style = _book_style(book)
    issues = _review_title(chapter.title or "", book_style=book_style, level="chapter", context=snap)
    issues.extend(_chapter_findings(chapter, markdown, book_style=book_style, context=snap, book_level=False))
    dims = _dimension_summaries(issues)
    return QualityReviewResult(detector_dimensions=dims, issues=issues[:40])


def _book_style(book: Book) -> str:
    raw = getattr(getattr(book, "book_type", None), "value", None) or getattr(book, "book_type", None) or ""
    text = str(raw).lower()
    if any(k in text for k in ("academic", "research", "monograph", "学术", "专著")):
        return "academic_monograph"
    if any(k in text for k in ("textbook", "教材", "course")):
        return "textbook"
    if any(k in text for k in ("technical", "tech", "技术")):
        return "technical_deep_dive"
    if any(k in text for k in ("guide", "practical", "实用", "指南")):
        return "practical_guide"
    if any(k in text for k in ("commentary", "opinion", "观点")):
        return "opinion_commentary"
    if any(k in text for k in ("business", "management", "商业", "管理")):
        return "business_management"
    if any(k in text for k in ("science", "科普")):
        return "popular_science"
    return "practical_guide"


def _chapter_markdown(chapter: Chapter) -> str:
    content = chapter.content if isinstance(chapter.content, dict) else None
    return chapter_content_to_markdown(content)


def _review_title(
    title: str,
    *,
    book_style: str,
    level: str,
    context: dict[str, Any],
    chapter_index: int | None = None,
) -> list[dict[str, Any]]:
    title = (title or "").strip()
    if not title:
        return []
    findings: list[dict[str, Any]] = []
    benchmark = title_benchmark_for_style(book_style)
    min_len, max_len, hard_max = title_limits_from_benchmark(book_style, benchmark)
    benchmark_note = benchmark.note()
    benchmark_evidence = {"title_benchmark": benchmark.evidence()}
    normalized_len = _cjk_len(title)
    marketing = [w for w in _MARKETING_WORDS if w in title]
    abstract_hits = [w for w in _ABSTRACT_TITLE_WORDS if w in title]
    has_concrete_signal = bool(re.search(r"[A-Za-z0-9]|\d|AI|大模型|人工智能|出版|写作|教育|企业|知识|技术|方法|指南", title))

    if normalized_len > hard_max or len(marketing) >= 1:
        findings.append(
            _finding(
                category="title_quality",
                dimension="logic_structure",
                issue_type="title_marketing_or_too_long",
                severity="medium",
                title="标题过长或营销化",
                detail=(
                    f"标题「{title}」长度约 {normalized_len} 个中文字符"
                    + (f"，且包含营销化词语：{ '、'.join(marketing) }。" if marketing else "。")
                    + benchmark_note
                ),
                quote=title,
                detector="title_reviewer",
                product_dimension="goal_alignment",
                fix_capability="choice_then_apply",
                why="标题会影响读者对书类和内容边界的判断，营销化表达也会削弱出版图书的可信度。",
                action_options=[
                    _action("keep", "保留原题", "确认该标题符合定位后保留", "observe"),
                    _action("compress_title", "压缩标题", "保留对象和场景，删除营销词", "choose"),
                    _action("add_subtitle", "调整副标题", "把场景、方法或读者放入副标题", "choose"),
                ],
                chapter_index=chapter_index,
                evidence_extra=benchmark_evidence,
            )
        )
    elif normalized_len < min_len and level == "book":
        findings.append(
            _finding(
                category="title_quality",
                dimension="logic_structure",
                issue_type="title_too_short",
                severity="low",
                title="标题信息略少",
                detail=f"标题「{title}」较短，可能没有充分交代对象、场景或读者。{benchmark_note}",
                quote=title,
                detector="title_reviewer",
                product_dimension="goal_alignment",
                fix_capability="choice_then_apply",
                why="标题信息不足会降低读者对书籍边界和价值的判断效率。",
                action_options=[
                    _action("keep", "保留原题", "标题已被用户确认时保留", "observe"),
                    _action("add_scope", "补充范围", "补充对象、场景或方法", "choose"),
                ],
                chapter_index=chapter_index,
                evidence_extra=benchmark_evidence,
            )
        )

    if abstract_hits and not has_concrete_signal:
        findings.append(
            _finding(
                category="title_quality",
                dimension="logic_structure",
                issue_type="title_abstract_only",
                severity="medium",
                title="标题对象不清",
                detail=f"标题「{title}」包含抽象价值词，但缺少清晰对象、范围或方法。",
                quote=title,
                detector="title_reviewer",
                product_dimension="goal_alignment",
                fix_capability="choice_then_apply",
                why="抽象标题容易让读者无法判断本书实际讨论什么。",
                action_options=[_action("add_object", "补充对象", "补充研究对象、场景或读者", "choose")],
                chapter_index=chapter_index,
            )
        )

    if book_style == "academic_monograph" and _has_undefined_theory_title(title, context):
        findings.append(
            _finding(
                category="title_quality",
                dimension="factual_support",
                issue_type="undefined_theory_term",
                severity="needs_verification",
                title="标题理论名词待核验",
                detail=f"标题「{title}」包含疑似理论、模型或框架名，但当前资料中未看到明确定义或来源。",
                quote=title,
                detector="title_reviewer",
                product_dimension="evidence_citation",
                fix_capability="manual_only",
                verification_status="needs_verification",
                why="学术标题中的理论名词会被读者视为核心概念，缺少定义或来源会影响可信度。",
                action_options=[
                    _action("bind_definition", "补充定义来源", "从文献或用户资料中确认概念来源", "manual"),
                    _action("rename_generic", "改为通用表述", "不使用未经确认的理论命名", "choose"),
                ],
                chapter_index=chapter_index,
            )
        )
    return findings


def _chapter_findings(
    chapter: Chapter,
    markdown: str,
    *,
    book_style: str,
    context: dict[str, Any],
    book_level: bool,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    findings.extend(_review_paragraph_echo(markdown, book_style=book_style, chapter_index=chapter.index if book_level else None))
    findings.extend(_review_reference_authenticity(markdown, chapter_index=chapter.index if book_level else None))
    findings.extend(_review_layout(markdown, chapter_index=chapter.index if book_level else None))
    findings.extend(_review_ai_text_risk(markdown, book_style=book_style, chapter_index=chapter.index if book_level else None))
    return findings


def _review_paragraph_echo(markdown: str, *, book_style: str, chapter_index: int | None = None) -> list[dict[str, Any]]:
    paragraphs = [p for p in parse_paragraphs(markdown) if _is_body_paragraph(p.text)]
    findings: list[dict[str, Any]] = []
    for prev, cur in zip(paragraphs, paragraphs[1:]):
        if min(len(prev.text), len(cur.text)) < 24:
            continue
        sim = max(
            _ngram_similarity(prev.text, cur.text),
            SequenceMatcher(None, _normalize(prev.text), _normalize(cur.text)).ratio(),
        )
        if sim < 0.72:
            continue
        is_near_duplicate = sim >= 0.88
        findings.append(
            _finding(
                category="paragraph_echo",
                dimension="style_consistency",
                issue_type="paragraph_adjacent_echo" if not is_near_duplicate else "paragraph_near_duplicate",
                severity="medium" if not is_near_duplicate else "high",
                title="相邻段落重复",
                detail=f"第 {prev.paragraph_index + 1} 与第 {cur.paragraph_index + 1} 个段落相似度较高，后一段缺少明显新增信息。",
                quote=cur.text[:500],
                detector="paragraph_echo_reviewer",
                product_dimension="structure_progress",
                fix_capability="choice_then_apply" if not is_near_duplicate else "preview_apply",
                why="重复段落会降低章节推进效率，读者难以判断后一段是否提供了新信息。",
                action="delete" if is_near_duplicate else "revise",
                action_options=[
                    _action("merge", "合并重复信息", "保留新增信息并压缩重复表达", "preview" if is_near_duplicate else "choose"),
                    _action("keep", "保留", "如果这是教材必要复述或修辞排比，可保留", "observe"),
                ],
                paragraph_index=cur.paragraph_index,
                char_start=cur.char_start,
                char_end=cur.char_end,
                chapter_index=chapter_index,
                confidence=min(0.95, sim),
            )
        )
        if len(findings) >= 8:
            break
    findings.extend(_review_repeated_skeleton(paragraphs, chapter_index=chapter_index))
    return findings[:10]


def _review_repeated_skeleton(paragraphs: list[Any], *, chapter_index: int | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    window = paragraphs[:60]
    starts: dict[str, list[Any]] = {}
    for p in window:
        m = re.match(r"^\s*(从.{1,8}角度看|从.{1,8}来看|一方面|另一方面|首先|其次|最后)", p.text)
        if not m:
            continue
        key = re.sub(r"从.{1,8}(角度看|来看)", "从X来看", m.group(1))
        starts.setdefault(key, []).append(p)
    for key, rows in starts.items():
        if len(rows) < 3:
            continue
        quote = "\n".join(r.text[:80] for r in rows[:3])
        findings.append(
            _finding(
                category="paragraph_echo",
                dimension="style_consistency",
                issue_type="repeated_skeleton",
                severity="medium",
                title="句式骨架重复",
                detail=f"连续或近距离段落多次使用「{key}」类句式，需要判断是否有真实分论点差异。",
                quote=quote,
                detector="paragraph_echo_reviewer",
                product_dimension="structure_progress",
                fix_capability="choice_then_apply",
                why="同类句式循环容易形成机械铺排，如果没有新增信息，会削弱论证推进。",
                action_options=[
                    _action("compress", "压缩重复开头", "保留分论点，减少机械句式", "choose"),
                    _action("add_evidence", "补充差异证据", "为各分论点补充不同例证或条件", "manual"),
                    _action("keep", "保留", "如果是有意排比并增强表达，可保留", "observe"),
                ],
                paragraph_index=rows[0].paragraph_index,
                char_start=rows[0].char_start,
                char_end=rows[-1].char_end,
                chapter_index=chapter_index,
                confidence=0.78,
            )
        )
    return findings[:4]


def _review_reference_authenticity(markdown: str, *, chapter_index: int | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    paragraphs = parse_paragraphs(markdown)
    for p in paragraphs:
        text = p.text
        has_precise_data = bool(_PERCENT_RE.search(text) or any(m in text for m in _UNSOURCED_MARKERS))
        if not has_precise_data or _CITATION_MARKER_RE.search(text):
            continue
        findings.append(
            _finding(
                category="reference_authenticity",
                dimension="citation_sources",
                issue_type="missing_citation",
                severity="needs_verification",
                title="数据或判断缺少来源",
                detail="本段包含具体比例、研究判断或泛称来源，但未看到可核验引用。",
                quote=text[:500],
                detector="reference_authenticity_reviewer",
                product_dimension="evidence_citation",
                fix_capability="choice_then_apply",
                verification_status="needs_verification",
                why="具体数据和研究判断会直接影响读者对论证可信度的判断，缺少来源时不应自动改写成空泛表述。",
                action="choose",
                action_options=default_data_action_options(),
                paragraph_index=p.paragraph_index,
                char_start=p.char_start,
                char_end=p.char_end,
                chapter_index=chapter_index,
                confidence=0.82,
            )
        )
        if len(findings) >= 8:
            break

    for match in list(_REFERENCE_LINE_RE.finditer(markdown))[:12]:
        line = match.group(0).strip()
        after = markdown[match.end() : match.end() + 260]
        if "摘要" in after:
            continue
        findings.append(
            _finding(
                category="reference_authenticity",
                dimension="citation_sources",
                issue_type="reference_missing_abstract",
                severity="needs_verification",
                title="文献元数据缺摘要",
                detail="学术文献条目未包含摘要。用于核心论证时，建议用户从知网等来源导出含摘要格式。",
                quote=line[:500],
                detector="reference_authenticity_reviewer",
                product_dimension="evidence_citation",
                fix_capability="choice_then_apply",
                verification_status="needs_verification",
                why="摘要能帮助系统判断文献与章节论证是否相关，缺摘要时只能作为弱依据。",
                action_options=[
                    _action("upload_cnki_abstract", "补充含摘要导出", "从知网导出含摘要的文献格式后上传", "manual"),
                    _action("mark_weak_source", "标为弱依据", "暂不作为核心论证强依据", "choose"),
                ],
                chapter_index=chapter_index,
                confidence=0.75,
            )
        )
    return findings[:12]


def _review_layout(markdown: str, *, chapter_index: int | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for label, regex in (("图", _FIGURE_RE), ("表", _TABLE_RE)):
        nums = [(int(m.group(1)), int(m.group(2)), m.group(0), m.start(), m.end()) for m in regex.finditer(markdown)]
        if len(nums) < 2:
            continue
        serials = [n[1] for n in nums]
        duplicate = len(set((n[0], n[1]) for n in nums)) != len(nums)
        out_of_order = serials != sorted(serials)
        gap = serials and (max(serials) - min(serials) + 1 != len(set(serials)))
        if not (duplicate or out_of_order or gap):
            continue
        first = nums[0]
        findings.append(
            _finding(
                category="layout_format",
                dimension="figure_quality",
                issue_type="figure_table_numbering",
                severity="medium",
                title=f"{label}编号可能不连续",
                detail=f"检测到{label}编号存在重复、乱序或跳号，建议调用图表一键排序后预览。",
                quote=first[2],
                detector="layout_reviewer",
                product_dimension="publication_delivery",
                fix_capability="preview_apply",
                why="图表编号不连续会影响正文引用和出版交付检查。",
                action_options=[
                    _action("normalize_figure_table_order", "一键排序", "调用已有图表排序函数并预览 diff", "preview")
                ],
                char_start=first[3],
                char_end=first[4],
                chapter_index=chapter_index,
                confidence=0.9,
            )
        )
    findings.extend(_review_first_line_indent(markdown, chapter_index=chapter_index))
    return findings[:8]


def _review_first_line_indent(markdown: str, *, chapter_index: int | None = None) -> list[dict[str, Any]]:
    paragraphs = [p for p in parse_paragraphs(markdown) if _is_body_paragraph(p.text)]
    if len(paragraphs) < 4:
        return []
    missing = [p for p in paragraphs if not (p.text.startswith("  ") or p.text.startswith("\u3000\u3000"))]
    # Markdown drafts often omit visual indentation. Only flag when a document is
    # clearly using indentation elsewhere but many body paragraphs miss it.
    has_indent = len(missing) < len(paragraphs)
    if not has_indent or len(missing) / max(1, len(paragraphs)) < 0.35:
        return []
    p = missing[0]
    return [
        _finding(
            category="layout_format",
            dimension="language_grammar",
            issue_type="first_line_indent",
            severity="low",
            title="正文首行缩进不一致",
            detail="部分普通正文段落缺少首行缩进，建议按全书体例统一。",
            quote=p.text[:300],
            detector="layout_reviewer",
            product_dimension="publication_delivery",
            fix_capability="preview_apply",
            why="正文缩进不一致会影响版面统一性和出版交付质量。",
            action_options=[_action("normalize_first_line_indent", "统一缩进", "预览后统一普通正文首行缩进", "preview")],
            paragraph_index=p.paragraph_index,
            char_start=p.char_start,
            char_end=p.char_end,
            chapter_index=chapter_index,
            confidence=0.72,
        )
    ]


def _review_ai_text_risk(markdown: str, *, book_style: str, chapter_index: int | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for p in parse_paragraphs(markdown):
        text = p.text
        if not _is_body_paragraph(text):
            continue
        hits = [phrase for phrase in _GENERIC_AI_PHRASES if phrase in text]
        if len(hits) < 2 and not ("机遇也是挑战" in text and "不断探索" in text):
            continue
        replacement = _rewrite_generic_ai_summary(text)
        findings.append(
            _finding(
                category="ai_text_risk",
                dimension="ai_signature",
                issue_type="generic_summary",
                severity="medium",
                title="总结表达偏空泛",
                detail=f"本段包含较多模板化总结表达：{'、'.join(hits[:4])}。",
                quote=text[:500],
                detector="ai_text_risk_reviewer",
                product_dimension="argument_quality",
                fix_capability="preview_apply",
                why="空泛总结会降低信息密度，让读者难以判断本段提供了什么新判断或行动含义。",
                action="replace",
                replacement_text=replacement,
                action_options=[
                    _action("compress", "压实表达", "删除无信息套话，保留必要结论", "preview"),
                    _action("keep", "保留", "如果该段承担章节收束功能，可保留", "observe"),
                ],
                paragraph_index=p.paragraph_index,
                char_start=p.char_start,
                char_end=p.char_end,
                chapter_index=chapter_index,
                confidence=0.76,
            )
        )
        if len(findings) >= 6:
            break
    return findings


def _rewrite_generic_ai_summary(text: str) -> str:
    result = (text or "").strip()
    replacements = (
        (r"^\s*(综上所述|总的来说)[，,、\s]*", ""),
        (r"(值得注意的是|在这个过程中|从某种意义上说)[，,、\s]*", ""),
        (r"全面、系统、深入地理解", "明确识别"),
        (r"全面、系统、深入", "具体"),
        (r"既是机遇也是挑战", "带来机会，也形成新的约束"),
        (r"机遇也是挑战", "机会与约束并存"),
        (r"不断探索", "持续验证"),
    )
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    result = re.sub(r"[，,]\s*。", "。", result)
    result = re.sub(r"。{2,}", "。", result)
    result = re.sub(r"\s+", " ", result).strip()
    if result == (text or "").strip():
        return result
    return result


def _dimension_summaries(issues: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    by_dimension: dict[str, list[dict[str, Any]]] = {}
    for item in issues:
        by_dimension.setdefault(str(item.get("dimension") or "language_grammar"), []).append(item)
    for key, rows in by_dimension.items():
        out[key] = {
            "raw_score": max(55, 92 - min(30, sum(_penalty_for_issue(i) for i in rows))),
            "summary": f"确定性审校器发现 {len(rows)} 个候选问题。",
            "confidence": 0.76,
            "status": "completed",
            "detector": "quality_reviewers",
        }
    return out


def _title_limits(book_style: str) -> tuple[int, int, int]:
    return {
        "popular_science": (4, 14, 36),
        "opinion_commentary": (4, 14, 36),
        "practical_guide": (6, 18, 42),
        "technical_deep_dive": (6, 22, 48),
        "academic_monograph": (10, 30, 56),
        "textbook": (4, 20, 42),
        "reference_tool": (4, 20, 42),
        "business_management": (6, 18, 42),
    }.get(book_style, (6, 20, 42))


def _has_undefined_theory_title(title: str, context: dict[str, Any]) -> bool:
    if not any(s in title for s in _THEORY_SUFFIXES):
        return False
    blob = " ".join(str(x) for x in (context.get("terms") or context.get("term_base") or context.get("must_keep") or []))
    return title not in blob


def _cjk_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _ngram_similarity(a: str, b: str, n: int = 3) -> float:
    sa = _ngrams(_normalize(a), n)
    sb = _ngrams(_normalize(b), n)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _ngrams(text: str, n: int) -> set[str]:
    if len(text) <= n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(0, len(text) - n + 1)}


def _normalize(text: str) -> str:
    return re.sub(r"[\s，。！？；：、“”‘’（）()\[\]【】,.!?;:\"'\-—_]+", "", text or "").lower()


def _is_body_paragraph(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 12:
        return False
    return not (
        t.startswith("#")
        or t.startswith("|")
        or t.startswith("```")
        or re.match(r"^\s*[-*+]\s+", t)
        or re.match(r"^\s*\d+[.)、]\s+", t)
        or re.match(r"^\s*(图|表)\s*\d", t)
        or re.match(r"^\s*\[\d+\]", t)
        or t.lower().startswith(("http://", "https://", "doi:"))
    )


def _penalty_for_issue(item: dict[str, Any]) -> int:
    sev = str(item.get("severity") or "medium")
    return {"high": 10, "medium": 6, "low": 3, "needs_verification": 5}.get(sev, 4)


def _action(action_id: str, label: str, description: str, action_type: str) -> dict[str, str]:
    return {"id": action_id, "label": label, "description": description, "action_type": action_type}


def _finding(
    *,
    category: str,
    dimension: str,
    issue_type: str,
    severity: str,
    title: str,
    detail: str,
    quote: str,
    detector: str,
    product_dimension: str,
    fix_capability: str,
    why: str,
    action_options: list[dict[str, str]],
    action: str = "revise",
    replacement_text: str = "",
    verification_status: str | None = None,
    paragraph_index: int | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
    chapter_index: int | None = None,
    confidence: float = 0.72,
    evidence_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quality_evidence = {
        "product_dimension": product_dimension,
        "why_it_matters": why,
        "action_options": action_options,
        "fix_capability": fix_capability,
    }
    if evidence_extra:
        quality_evidence.update(evidence_extra)
    if verification_status:
        quality_evidence["verification_status"] = verification_status
    item: dict[str, Any] = {
        "category": category,
        "dimension": dimension,
        "issue_type": issue_type,
        "severity": severity,
        "title": title,
        "detail": detail,
        "explanation": detail,
        "quote": quote,
        "action": action,
        "action_type": action,
        "replacement_text": replacement_text,
        "detector": detector,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "quality_evidence": quality_evidence,
        "product_dimension": product_dimension,
        "why_it_matters": why,
        "action_options": action_options,
        "fix_capability": fix_capability,
        "chapter_index": chapter_index,
    }
    if verification_status:
        item["verification_status"] = verification_status
    if paragraph_index is not None:
        item["paragraph_index"] = paragraph_index
    if char_start is not None:
        item["char_start"] = char_start
    if char_end is not None:
        item["char_end"] = char_end
    return item
