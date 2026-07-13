# Outline generation — JSON schema + 体裁化大纲指令由 style_prompts 注入

OUTLINE_FALLBACK_STYLE = """
你是一位专业的图书策划编辑，擅长设计清晰、有说服力的书籍结构。
你的任务是根据用户提供的主题和要求，生成一份详细的书籍大纲。
""".strip()

OUTLINE_TITLE_RULES = """
【章/节标题规范（必须遵守）】
- 禁止使用「主题：副标题」「概念：说明」等冒号对仗式标题（AI 味重）
- 禁止使用破折号拼接两个抽象短语（如「认知跃迁——理解大模型」）
- 章标题可带「第X章」前缀；章标题 6-20 字单句，不要副标题
- 【节标题编号强制】sections 中每个 title 必须以「第X节 」开头（X 为本章内节序号，用中文数字）：
  · 第 1 章第 1 节 → "第一节 具体标题"
  · 第 1 章第 2 节 → "第二节 具体标题"
  · 第 3 章第 1 节 → "第一节 具体标题"（每章节序号从一节重新计）
  · 禁止使用 1.1、2.3 等小数编号；正文内更深层级用「一、」「（一）」「1．」「（1）」
- 小节摘要写在 summary 字段，不要写进 title
- 标题应像人写的篇名，不要营销口号
""".strip()

OUTLINE_JSON_INSTRUCTION = """
输出格式要求（严格遵守，只返回 JSON，不要任何解释文字、不要代码块）：
- 字符串值内如需引号，请用「」或『』，禁止在 JSON 字符串里写未转义的英文双引号 "
{
  "title": "书名建议",
  "preface_brief": "前言写作要点2-4句（必填，散文语气，不要条目结构，与全书主题和大纲呼应）",
  "total_chapters": 数字,
  "estimated_words": 数字,
  "chapters": [
    {
      "index": 1,
      "title": "第一章 当机器开始读懂上下文",
      "summary": "本章核心内容摘要（100-150字）",
      "key_points": ["核心论点1", "核心论点2"],
      "estimated_words": 数字,
      "sections": [
        {"title": "第一节 注意力机制为何改变一切", "summary": "本节摘要（50字）"},
        {"title": "第二节 从静态词向量到上下文窗口", "summary": "本节摘要（50字）"}
      ],
      "column_labels": ["操作步骤", "命令示例", "故障排查", "本章小结"]
    }
  ]
}
每章可选 column_labels（2-6 个短标签）：本章正文建议采用的栏目/呈现块名称，如「操作步骤 · 案例 · 小结」；纯理论章可省略或给 2-3 个即可。
""".strip()

# 兼容旧代码引用：体裁缺失时的默认系统词 = 泛用编辑 + JSON
OUTLINE_SYSTEM_PROMPT = (OUTLINE_FALLBACK_STYLE + "\n\n" + OUTLINE_TITLE_RULES + "\n\n" + OUTLINE_JSON_INSTRUCTION).strip()

# jsonschema draft-07 minimal validation for outline root
OUTLINE_JSON_SCHEMA: dict = {
    "type": "object",
    "required": ["title", "preface_brief", "total_chapters", "estimated_words", "chapters"],
    "properties": {
        "title": {"type": "string"},
        "preface_brief": {"type": "string"},
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
                    "column_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 8,
                    },
                },
            },
        },
    },
}
