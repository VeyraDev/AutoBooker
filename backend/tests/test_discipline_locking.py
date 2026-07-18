import json
from types import SimpleNamespace
from uuid import uuid4

from app.models.book import BookType
from app.services.setup_recommend_service import recommend_book_setup
from app.services.writing.project_seed import infer_and_apply_book_settings


class _Db:
    def __init__(self):
        self.commits = 0
        self.refreshed = []

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


def _book(**overrides):
    data = {
        "id": uuid4(),
        "title": "智能体记忆与图书写作",
        "book_type": BookType.nonfiction,
        "style_type": "popular_science",
        "discipline": None,
        "disciplines": None,
        "target_audience": None,
        "topic_tags": None,
        "topic_brief": None,
        "user_material": None,
        "citation_style": None,
        "target_words": None,
        "ai_inferred_settings": None,
        "setup_recommendation_cache": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_setup_recommend_caps_disciplines_and_keeps_candidate_reasons(monkeypatch):
    payload = {
        "recommended_tags": ["智能体记忆", "图书写作"],
        "target_audience": "面向希望使用 AI 辅助写作的作者。",
        "disciplines": ["计算机科学", "出版编辑学", "认知科学", "管理学"],
        "discipline_candidates": [
            {
                "name": "计算机科学",
                "reason": "智能体记忆涉及系统架构和模型能力边界。",
                "ambiguity_note": "",
            },
            {
                "name": "出版编辑学",
                "reason": "图书质量判断需要出版流程与编辑规范。",
                "ambiguity_note": "“审校”需区别技术校验与编辑审读。",
            },
            {"name": "认知科学", "reason": "记忆概念存在跨学科解释。"},
            {"name": "管理学", "reason": "不应进入默认候选。"},
        ],
        "discipline_confirmation_note": "请先确认主领域。",
        "topic_brief": "讨论智能体记忆如何服务图书写作。",
    }

    class _Client:
        def chat_completion(self, *_args, **_kwargs):
            return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr("app.services.setup_recommend_service.LLMClient", lambda: _Client())
    monkeypatch.setattr(
        "app.services.setup_recommend_service.resolve_book_outline_model",
        lambda *_args, **_kwargs: "test-model",
    )

    book = _book()
    db = _Db()
    result = recommend_book_setup(book, SimpleNamespace(id=uuid4()), db)  # type: ignore[arg-type]

    assert result["disciplines"] == ["计算机科学", "出版编辑学", "认知科学"]
    assert [c["name"] for c in result["discipline_candidates"]] == ["计算机科学", "出版编辑学", "认知科学"]
    assert result["discipline_candidates"][1]["ambiguity_note"] == "“审校”需区别技术校验与编辑审读。"
    assert book.setup_recommendation_cache["payload"]["discipline_confirmation_note"] == "请先确认主领域。"
    assert db.commits == 1

    cached = recommend_book_setup(book, SimpleNamespace(id=uuid4()), db)  # type: ignore[arg-type]
    assert cached["from_cache"] is True
    assert cached["discipline_candidates"][0]["reason"] == "智能体记忆涉及系统架构和模型能力边界。"
    assert db.commits == 1


def test_project_seed_inference_locks_disciplines_from_user_intent(monkeypatch):
    payload = {
        "book_type": "academic",
        "style_type": "technical_deep_dive",
        "target_words": 180000,
        "target_audience": "面向智能体系统研究者和图书出版产品团队。",
        "disciplines": ["计算机科学", "出版编辑学", "认知科学", "心理学"],
        "discipline_candidates": [
            {"name": "计算机科学", "reason": "需要约束智能体、记忆和工具调用等术语。"},
            {"name": "出版编辑学", "reason": "需要约束审校、版式和交付质量判断。"},
            {"name": "认知科学", "reason": "记忆概念存在跨学科含义。"},
        ],
        "topic_tags": ["智能体记忆", "审校工作流"],
        "citation_style": "gb_t7714",
        "topic_brief": "研究智能体记忆在图书写作流程中的作用。",
    }

    class _Client:
        def chat_completion(self, *_args, **_kwargs):
            return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr("app.services.writing.project_seed.LLMClient", lambda: _Client())

    book = _book(title="书稿1", topic_brief="智能体记忆辅助图书写作")
    seed = infer_and_apply_book_settings(book, "test-model")

    assert "智能体记忆" in seed
    assert book.book_type == BookType.academic
    assert book.style_type == "technical_deep_dive"
    assert book.disciplines == ["计算机科学", "出版编辑学", "认知科学"]
    assert book.discipline == "计算机科学"
    assert book.ai_inferred_settings["discipline_candidates"][2]["name"] == "认知科学"
