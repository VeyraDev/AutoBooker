QUERY_REFINE_PROMPT = """
你是资料检索词编辑。根据书籍、章节和用户原话，生成适合当前查询意图的检索词。

只返回 JSON：
{{
  "refined_queries": ["中文技术检索词", "英文技术检索词", "..."],
  "must_include": ["必须包含的关键词"],
  "must_exclude": ["应排除的多义词或跑题词"]
}}

要求：
- 去掉无意义口语（如「怎样让城市更适合步行」→ 城市可步行性 / urban walkability）
- refined_queries 共 2~6 条；只有目标来源或主题确实需要时才生成英文词，不为凑数添加
- 保留人物、机构、事件、时间、学科术语和用户明确的范围
- must_exclude 用于避免多义词跑题（如「培养」排除教育学）

书名：{book_title}
书型：{book_type} / {style_type}
简介/材料：{user_material}
章节标题：{chapter_title}
章节摘要：{chapter_summary}
话题标签：{topic_tags}
用户原始检索意图：{raw_query}
""".strip()
