# Memory extraction after chapter generation

MEMORY_EXTRACT_PROMPT = """
阅读以下章节内容，提取以下信息并以 JSON 返回（只返回 JSON，不要解释）：
{
  "summary": "本章核心内容摘要（不超过200字）",
  "new_terms": {"术语": "定义"},
  "key_conclusions": ["结论1"],
  "style_sample": "本章首段文字",
  "chapter_hook": "章末留给下一章承接的具体悬念或未解决问题（一两句话，要具体可操作）；若无明确承接点则返回空字符串"
}

说明：
- new_terms 只收录专业学科术语、理论名、专名、人名机构名、用户指定表达或本书特殊定义；若无则返回 {}。
- 不收录日常表达、网络常用词、普通情绪词或常见社会话题词，不自动补英文或词典式定义。
- key_conclusions 为本章最重要的不超过 5 条结论。
- style_sample 用于风格锚定：请摘录本章正文第一段（不超过 300 字）；若本章无正文则返回空字符串。
- chapter_hook 供下一章开头接住：必须是具体事实/问题/未竟任务，禁止「下一章我们将继续」类空话。
""".strip()

MEMORY_JSON_SCHEMA: dict = {
    "type": "object",
    "required": ["summary", "new_terms", "key_conclusions", "style_sample", "chapter_hook"],
    "properties": {
        "summary": {"type": "string"},
        "new_terms": {"type": "object", "additionalProperties": {"type": "string"}},
        "key_conclusions": {"type": "array", "items": {"type": "string"}},
        "style_sample": {"type": "string"},
        "chapter_hook": {"type": "string"},
    },
}
