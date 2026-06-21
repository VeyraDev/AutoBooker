"""gpt-5 系列 temperature 兼容。"""

from app.llm.client import LLMClient


def test_gpt5_omits_temperature():
    assert LLMClient._openai_omit_temperature("openai", "gpt-5.5") is True
    assert LLMClient._openai_omit_temperature("openai", "o3-mini") is True
    assert LLMClient._openai_omit_temperature("openai", "gpt-4o") is False


def test_gateway_gpt_models_keep_openai_compatible_params():
    assert LLMClient._openai_omit_temperature("zeelin", "gpt-5.5") is False
    assert LLMClient._openai_uses_max_completion_tokens("zeelin", "gpt-5.5") is False
    assert LLMClient._openai_uses_max_completion_tokens("openai", "gpt-5.5") is True
