"""配图分阶段 Prompt 模板。"""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8")


def format_prompt(name: str, **fields: str) -> str:
    """安全填充 prompt，避免 JSON 花括号与 str.format 冲突。"""
    text = load_prompt(name)
    for key, value in fields.items():
        text = text.replace("{" + key + "}", str(value))
    return text
