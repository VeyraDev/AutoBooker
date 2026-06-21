from app.config import settings
from app.llm.providers import default_ai_model, get_provider_spec, llm_models_catalog, normalize_ai_model, provider_base_url


def test_zeelin_provider_registered_with_default_base_url(monkeypatch):
    monkeypatch.setattr(settings, "ZEELIN_API_KEY", "")
    monkeypatch.setattr(settings, "ZEELIN_BASE_URL", "")

    spec = get_provider_spec("zeelin")

    assert spec is not None
    assert spec.label == "智灵网关"
    assert spec.native_api == "openai"
    assert provider_base_url("zeelin") == "https://getways-jumu.zeelin.cn/v1"
    assert "qwen-plus" in spec.models


def test_zeelin_model_catalog_uses_provider_model_format(monkeypatch):
    monkeypatch.setattr(settings, "ZEELIN_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ZEELIN_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(settings, "ZEELIN_CHAT_MODEL", "DeepSeek-V4-Pro")

    catalog = llm_models_catalog()
    deepseek = next(p for p in catalog["providers"] if p["id"] == "deepseek")
    openai = next(p for p in catalog["providers"] if p["id"] == "openai")
    doubao = next(p for p in catalog["providers"] if p["id"] == "doubao")

    assert catalog["default"] == "zeelin:DeepSeek-V4-Pro"
    assert all(p["label"] != "智灵网关" for p in catalog["providers"])
    assert {"id": "DeepSeek-V4-Pro", "label": "DeepSeek V4 Pro", "value": "zeelin:DeepSeek-V4-Pro"} in deepseek["models"]
    assert {"id": "gpt-5.5", "label": "GPT-5.5", "value": "zeelin:gpt-5.5"} in openai["models"]
    assert {
        "id": "Doubao-seed-2-0-pro",
        "label": "Doubao Pro 128k",
        "value": "zeelin:Doubao-seed-2-0-pro",
    } in doubao["models"]
    assert normalize_ai_model("zeelin:qwen-plus") == "zeelin:qwen-plus"


def test_zeelin_is_default_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "ZEELIN_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ZEELIN_CHAT_MODEL", "DeepSeek-V4-Pro")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", "qwen-key")

    assert default_ai_model() == "zeelin:DeepSeek-V4-Pro"
