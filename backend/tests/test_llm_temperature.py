"""gpt-5 系列 temperature 兼容。"""

from app.llm.client import LLMClient


def test_gpt5_omits_temperature():
    assert LLMClient._openai_omit_temperature("openai", "gpt-5.5") is True
    assert LLMClient._openai_omit_temperature("openai", "o3-mini") is True
    assert LLMClient._openai_omit_temperature("openai", "gpt-4o") is False


def test_gateway_gpt_models_use_openai_completion_params():
    assert LLMClient._openai_omit_temperature("zeelin", "gpt-5.5") is True
    assert LLMClient._openai_uses_max_completion_tokens("zeelin", "gpt-5.5") is True
    assert LLMClient._openai_uses_max_completion_tokens("openai", "gpt-5.5") is True
    assert LLMClient._openai_uses_max_completion_tokens("zeelin", "DeepSeek-V4-Pro") is False


def test_deepseek_v4_model_detection():
    assert LLMClient._is_deepseek_v4_model("DeepSeek-V4-Pro") is True
    assert LLMClient._is_deepseek_v4_model("deepseek-v4-flash") is True
    assert LLMClient._is_deepseek_v4_model("deepseek-chat") is False


def test_gpt5_resolves_higher_completion_budget():
    assert LLMClient._resolve_openai_max_tokens("gpt-5.5", 4096) == 8192
    assert LLMClient._resolve_openai_max_tokens("gpt-5.5", 16384) == 16384
    assert LLMClient._resolve_openai_max_tokens("deepseek-chat", 4096) == 4096


def test_completion_budget_scales_with_chapter_length():
    assert LLMClient.completion_budget_for_chinese_words(3000, "deepseek-chat") == 10696
    gpt_budget = LLMClient.completion_budget_for_chinese_words(5500, "zeelin:gpt-5.5")
    assert gpt_budget > 24000
    assert gpt_budget <= 65536
