QUERY_REFINE_PROMPT = """
你是学术与技术文献检索专家。根据书籍/章节信息，生成适合 CrossRef、Semantic Scholar、arXiv、GitHub 的检索词。

只返回 JSON：
{{
  "refined_queries": ["中文技术检索词", "英文技术检索词", "..."],
  "must_include": ["必须包含的关键词"],
  "must_exclude": ["应排除的多义词或跑题词"]
}}

要求：
- 去掉口语（如「怎样培养」→ 大模型微调 / LLM fine-tuning）
- refined_queries 共 5~8 条：2~3 条中文放前面（维基等），**必须保留至少 3 条英文**（GitHub / CrossRef / arXiv 必需，不可省略）
- 英文词用技术术语，不要用纯中文翻译重复同一词条
- must_exclude 用于避免多义词跑题（如「培养」排除教育学）

书名：{book_title}
书型：{book_type} / {style_type}
简介/材料：{user_material}
章节标题：{chapter_title}
章节摘要：{chapter_summary}
话题标签：{topic_tags}
用户原始检索意图：{raw_query}
""".strip()
