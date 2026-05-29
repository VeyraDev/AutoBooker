"""中文繁简转换（维基等来源）。"""

from __future__ import annotations


def to_simplified(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    try:
        import zhconv

        return zhconv.convert(t, "zh-cn")
    except Exception:
        return text
