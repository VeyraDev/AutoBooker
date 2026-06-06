"""gpt-5 系列 temperature 兼容。"""

from app.llm.client import LLMClient


def test_gpt5_omits_temperature():
    assert LLMClient._openai_omit_temperature("gpt-5.5") is True
    assert LLMClient._openai_omit_temperature("o3-mini") is True
    assert LLMClient._openai_omit_temperature("gpt-4o") is False
