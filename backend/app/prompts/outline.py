# Outline generation — system prompt and JSON schema (jsonschema format)

OUTLINE_SYSTEM_PROMPT = """
你是一位专业的图书策划编辑，擅长设计清晰、有说服力的非虚构书籍结构。
你的任务是根据用户提供的主题和要求，生成一份详细的书籍大纲。

输出格式要求（严格遵守，只返回 JSON，不要任何解释文字、不要代码块）：
{
  "title": "书名建议",
  "total_chapters": 数字,
  "estimated_words": 数字,
  "chapters": [
    {
      "index": 1,
      "title": "第一章 章节标题",
      "summary": "本章核心内容摘要（100-150字）",
      "key_points": ["核心论点1", "核心论点2"],
      "estimated_words": 数字,
      "sections": [
        {"title": "1.1 节标题", "summary": "节摘要（50字）"}
      ]
    }
  ]
}
""".strip()

# jsonschema draft-07 minimal validation for outline root
OUTLINE_JSON_SCHEMA: dict = {
    "type": "object",
    "required": ["title", "total_chapters", "estimated_words", "chapters"],
    "properties": {
        "title": {"type": "string"},
        "total_chapters": {"type": "integer", "minimum": 1},
        "estimated_words": {"type": "integer", "minimum": 1000},
        "chapters": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["index", "title", "summary", "key_points", "estimated_words", "sections"],
                "properties": {
                    "index": {"type": "integer", "minimum": 1},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                    "estimated_words": {"type": "integer", "minimum": 100},
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["title", "summary"],
                            "properties": {
                                "title": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}
