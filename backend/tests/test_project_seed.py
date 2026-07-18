"""project_seed helpers."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.models.book import BookType
from app.services.writing.project_seed import (
    _coerce_book_type,
    _coerce_style,
    resolve_project_seed,
)


def test_resolve_project_seed_prefers_goal_over_placeholder_title():
    book = SimpleNamespace(
        id=uuid4(),
        title="书稿1",
        topic_brief=None,
        user_material=None,
    )

    class _Db:
        def query(self, _model):
            class Q:
                def filter(self, *_a, **_k):
                    return self

                def order_by(self, *_a, **_k):
                    return self

                def first(self):
                    return SimpleNamespace(raw_goal_text="写一本博士后技术研究报告")

            return Q()

    seed = resolve_project_seed(book, _Db())  # type: ignore[arg-type]
    assert "博士后" in seed
    assert "书稿1" not in seed


def test_resolve_project_seed_falls_back_to_topic_brief():
    book = SimpleNamespace(
        id=uuid4(),
        title="书稿1",
        topic_brief="Kubernetes 运维手册",
        user_material=None,
    )

    class _Db:
        def query(self, _model):
            class Q:
                def filter(self, *_a, **_k):
                    return self

                def order_by(self, *_a, **_k):
                    return self

                def first(self):
                    return None

            return Q()

    seed = resolve_project_seed(book, _Db())  # type: ignore[arg-type]
    assert seed == "Kubernetes 运维手册"


def test_coerce_book_type_and_style_for_handbook_and_report():
    assert _coerce_book_type("academic") == BookType.academic
    assert _coerce_style(BookType.nonfiction, "reference_tool") == "reference_tool"
    assert _coerce_style(BookType.nonfiction, "技术手册") == "reference_tool"
    assert _coerce_style(BookType.academic, "博士后") == "technical_deep_dive"
    assert _coerce_style(BookType.academic, "textbook") == "textbook"
