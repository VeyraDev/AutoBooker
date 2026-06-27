"""数据图自然语言脚本：供 no_layout Image API 路径使用。"""

from __future__ import annotations

import logging

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.prompts import format_prompt

logger = logging.getLogger(__name__)


def generate_data_chart_script(
    user_input: str,
    *,
    book_type: str = "",
    style_type: str = "",
    model: str = "",
    use_llm: bool = True,
) -> tuple[str, bool]:
    """Return (script_text, used_fallback)."""
    text = (user_input or "").strip()
    if not text:
        return "", True

    llm_model = (model or settings.intent_model).strip()
    if not use_llm or not llm_model or llm_model.lower() == "dummy":
        return text, True

    try:
        prompt = format_prompt(
            "data_chart_script",
            text=text[:3500],
            context="用于 AutoBooker 书籍配图生成。",
            book_type=book_type or "图书正文",
            style_type=style_type or "清晰、克制、适合书籍内页的数据图",
        )
        out = LLMClient().chat_completion(
            [
                {"role": "system", "content": "只输出自然语言数据图脚本，不要 JSON，不要代码。"},
                {"role": "user", "content": prompt},
            ],
            model=llm_model,
            max_tokens=3600,
            temperature=0.0,
        )
        script = (out or "").strip()
        if script:
            return script, False
        raise ValueError("数据图规划器返回空内容")
    except Exception as exc:
        logger.warning("data chart script planner failed: %s", exc)
        return text, True
