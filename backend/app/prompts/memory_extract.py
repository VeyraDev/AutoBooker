# Memory extraction after chapter generation

MEMORY_EXTRACT_PROMPT = """
阅读以下章节内容，提取以下信息并以 JSON 返回（只返回 JSON，不要解释）：
{
  "summary": "本章核心内容摘要（不超过200字）",
  "new_terms": {"术语": "定义"},
  "key_conclusions": ["结论1"],
  "style_sample": "本章首段文字"
}

说明：
- new_terms 为本章新出现的专业术语及简短定义；若无则返回 {}。
- key_conclusions 为本章最重要的不超过 5 条结论。
- style_sample 用于风格锚定：请摘录本章正文第一段（不超过 300 字）；若本章无正文则返回空字符串。
""".strip()

MEMORY_JSON_SCHEMA: dict = {
    "type": "object",
    "required": ["summary", "new_terms", "key_conclusions", "style_sample"],
    "properties": {
        "summary": {"type": "string"},
        "new_terms": {"type": "object", "additionalProperties": {"type": "string"}},
        "key_conclusions": {"type": "array", "items": {"type": "string"}},
        "style_sample": {"type": "string"},
    },
}
