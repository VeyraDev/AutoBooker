"""Tests for deterministic layout review applications."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.routers import review as review_router
from app.services.review.review_workspace_service import ReviewWorkspaceService
from app.services.review.layout_autofix import normalize_first_line_indent
from app.services.review_anchor import snapshot_hash
from app.services.review_apply import preview_full_chapter_application
from app.services.tiptap_convert import tiptap_json_to_markdown


def _paragraph(text: str, attrs: dict | None = None) -> dict:
    node = {"type": "paragraph", "content": [{"type": "text", "text": text}]}
    if attrs:
        node["attrs"] = attrs
    return node


def test_first_line_indent_normalizer_marks_body_paragraphs_only():
    doc = {
        "type": "doc",
        "content": [
            _paragraph("第一段正文需要统一首行缩进。"),
            _paragraph("图1-1：系统结构图", {"textAlign": "center"}),
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "小节"}]},
            _paragraph("[1]张三.人工智能研究[J].测试期刊,2024."),
            _paragraph("　　第二段已有手工缩进，需要转为结构化缩进。"),
        ],
    }

    result = normalize_first_line_indent("", doc)
    out = result["tiptap_json"]["content"]

    assert result["changed_count"] == 2
    assert out[0]["attrs"]["firstLineIndent"] is True
    assert "firstLineIndent" not in (out[1].get("attrs") or {})
    assert "firstLineIndent" not in (out[3].get("attrs") or {})
    assert out[4]["attrs"]["firstLineIndent"] is True
    assert out[4]["content"][0]["text"] == "第二段已有手工缩进，需要转为结构化缩进。"

    md = tiptap_json_to_markdown(result["tiptap_json"])
    assert "　　第一段正文需要统一首行缩进。" in md
    assert "　　第二段已有手工缩进，需要转为结构化缩进。" in md
    assert "　　图1-1" not in md


def test_full_chapter_preview_stores_full_after_and_tiptap_json():
    before = "第一段正文。\n\n第二段正文。"
    after_doc = {
        "type": "doc",
        "content": [
            _paragraph("第一段正文。", {"firstLineIndent": True}),
            _paragraph("第二段正文。", {"firstLineIndent": True}),
        ],
    }
    after = tiptap_json_to_markdown(after_doc)

    preview = preview_full_chapter_application(
        current_markdown=before,
        issue_snapshot_hash=snapshot_hash(before),
        result_markdown=after,
        apply_type="first_line_indent",
        result_tiptap_json=after_doc,
    )

    assert preview["before_hash"] == snapshot_hash(before)
    assert preview["after_hash"] == snapshot_hash(after)
    assert preview["diff"]["full_chapter"] is True
    assert preview["diff"]["full_after"] == after
    assert preview["diff"]["full_after_tiptap"] == after_doc
    assert preview["locator_strategy"] == "first_line_indent"


def test_router_layout_preview_for_first_line_indent_uses_full_chapter_application():
    book = SimpleNamespace(id=uuid4())
    ch = SimpleNamespace(
        index=1,
        content={
            "tiptap_json": {
                "type": "doc",
                "content": [_paragraph("第一段正文需要统一首行缩进。")],
            }
        },
    )
    current_md = "第一段正文需要统一首行缩进。"
    issue = SimpleNamespace(
        issue_type="first_line_indent",
        snapshot_hash=snapshot_hash(current_md),
        quality_evidence={"fix_capability": "preview_apply"},
    )

    preview = review_router._layout_preview_for_issue(book, ch, issue, current_md, SimpleNamespace())

    assert preview is not None
    assert preview["apply_type"] == "first_line_indent"
    assert preview["diff"]["full_chapter"] is True
    assert "　　第一段正文需要统一首行缩进。" in preview["result_markdown"]
    assert preview["warning"]["changed_count"] == 1


def test_workspace_first_line_indent_preview_uses_review_application(monkeypatch):
    created: dict = {}

    def fake_create_application(_db, **kwargs):
        created.update(kwargs)
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(
        "app.repositories.review_repository.create_application",
        fake_create_application,
    )

    class _Db:
        def flush(self):
            created["flushed"] = True

    book = SimpleNamespace(id=uuid4())
    ch = SimpleNamespace(
        id=uuid4(),
        index=1,
        content={"tiptap_json": {"type": "doc", "content": [_paragraph("第一段正文需要统一首行缩进。")]}},
    )
    review = SimpleNamespace(id=uuid4(), total_score=80, dimensions=[])
    current_md = "第一段正文需要统一首行缩进。"
    issue = SimpleNamespace(
        id=uuid4(),
        issue_type="first_line_indent",
        dimension="language_grammar",
        snapshot_hash=snapshot_hash(current_md),
        quality_evidence={"fix_capability": "preview_apply"},
        paragraph_index=0,
        paragraph_id=None,
        quote="第一段正文需要统一首行缩进。",
    )

    result = ReviewWorkspaceService(_Db())._preview_first_line_indent_fix(  # type: ignore[arg-type]
        book,
        ch,
        review,
        issue,
        current_md,
    )

    assert result["preview_kind"] == "replace"
    assert result["locator_strategy"] == "first_line_indent"
    assert "　　第一段正文需要统一首行缩进。" in result["result_markdown"]
    assert created["apply_type"] == "first_line_indent"
    assert created["diff"]["full_chapter"] is True
    assert created["warning"]["changed_count"] == 1
    assert created["flushed"] is True


def test_workspace_generic_summary_preview_uses_deterministic_replacement(monkeypatch):
    created: dict = {}

    def fake_create_application(_db, **kwargs):
        created.update(kwargs)
        return SimpleNamespace(id=uuid4())

    def fail_llm_apply(*args, **kwargs):
        raise AssertionError("generic_summary should not call LLM when replacement_text is available")

    monkeypatch.setattr(
        "app.repositories.review_repository.create_application",
        fake_create_application,
    )
    monkeypatch.setattr("app.services.review_apply.apply_review_issue_text", fail_llm_apply)

    current_md = (
        "综上所述，人工智能的发展对于企业来说既是机遇也是挑战。"
        "我们需要全面、系统、深入地理解这一变化，并在实践中不断探索。"
    )
    replacement = (
        "人工智能的发展对于企业来说带来机会，也形成新的约束。"
        "我们需要明确识别这一变化，并在实践中持续验证。"
    )
    book = SimpleNamespace(id=uuid4())
    ch = SimpleNamespace(id=uuid4(), book_id=book.id, index=1, content={"text": current_md})
    review = SimpleNamespace(id=uuid4(), total_score=80, dimensions=[])
    issue = SimpleNamespace(
        id=uuid4(),
        chapter_id=ch.id,
        review_id=review.id,
        issue_type="generic_summary",
        dimension="ai_signature",
        title="总结表达偏空泛",
        explanation="本段包含较多模板化总结表达。",
        quote=current_md,
        replacement_text=replacement,
        action="replace",
        snapshot_hash=snapshot_hash(current_md),
        quality_evidence={"fix_capability": "preview_apply", "product_dimension": "argument_quality"},
        paragraph_index=0,
        paragraph_id=None,
        char_start=0,
        char_end=len(current_md),
    )

    class _Db:
        def get(self, model, row_id):
            name = getattr(model, "__name__", "")
            if name == "ChapterReviewIssue" and row_id == issue.id:
                return issue
            if name == "Chapter" and row_id == ch.id:
                return ch
            if name == "ChapterReview" and row_id == review.id:
                return review
            return None

        def flush(self):
            created["flushed"] = True

    result = ReviewWorkspaceService(_Db()).apply_finding(  # type: ignore[arg-type]
        book,
        issue.id,
        chat_model="unused",
    )

    assert result["preview_kind"] == "replace"
    assert result["result_text"] == replacement
    assert replacement in result["result_markdown"]
    assert created["apply_type"] == "replace"
    assert created["diff"]["after"] == replacement
    assert created["flushed"] is True
