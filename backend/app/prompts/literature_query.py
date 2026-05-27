QUERY_REFINE_PROMPT = """
你是学术与技术文献检索专家。根据书籍/章节信息，生成适合 CrossRef、Semantic Scholar、arXiv、GitHub 的检索词。

只返回 JSON：
{{
  "refined_queries": ["英文或中文技术检索词", "..."],
  "must_include": ["必须包含的关键词"],
  "must_exclude": ["应排除的多义词或跑题词"]
}}

要求：
- 去掉口语（如「怎样培养」→ fine-tuning / LLM training）
- 至少 2 条英文技术词，必要时保留 1 条中文
- refined_queries 3~6 条，从宽泛到精确
- must_exclude 用于避免多义词跑题（如「培养」排除教育学）

书名：{book_title}
书型：{book_type} / {style_type}
简介/材料：{user_material}
章节标题：{chapter_title}
章节摘要：{chapter_summary}
话题标签：{topic_tags}
用户原始检索意图：{raw_query}
""".strip()
