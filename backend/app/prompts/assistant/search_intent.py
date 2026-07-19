SEARCH_INTENT_PROMPT = """你是检索意图识别器。根据用户原话抽取结构化 SearchIntent。

只返回 JSON：
{{
  "search_type": "person_profile|person_works|literature|book|event_news|organization|government_data|industry_report|technical|web",
  "person_name": "人物姓名（去称谓后的核心名；非人物检索可为空）",
  "person_name_raw": "用户提到的姓名原样",
  "institution": "机构/单位或 null",
  "role": "职称/角色或 null",
  "topic": "研究方向/主题或 null",
  "language": ["zh", "en"],
  "source_types": ["paper", "book", "news", "government", "industry_report", "technical", "web"],
  "require_author_match": true,
  "needs_disambiguation": false,
  "display_query": "保留机构+姓名+角色的完整检索表述"
}}

规则：
- 不要用正则思维硬拆；理解复合描述（如「清华大学某某教授深度学习」）。
- person_profile：人物经历、访谈、任职与公开资料；person_works：人物作品清单。
- literature：主题学术文献；book：图书元数据；event_news：事件与新闻访谈。
- organization：机构资料；government_data：政策与官方数据；industry_report：行业报告。
- technical：技术文档、代码和官方开发资料；无法明确归类才用 web。
- 禁止因为出现人名就默认 person_works，也不得把“没有论文”解释为“没有公开资料”。
- needs_disambiguation：姓名过泛或可能多人时为 true。
- display_query 尽量保留完整上下文，便于百科/网页消歧。

search_type 提示：{search_type_hint}
用户原话：{raw_query}
""".strip()


SEARCH_QUERIES_PERSON_PROMPT = """你是人物作品检索词生成器（对齐设定页「生成检索词」能力）。

根据 SearchIntent 生成多条检索词，覆盖学术库、百科、机构主页、网页。

只返回 JSON：
{{
  "refined_queries": ["检索词1", "检索词2", "..."]
}}

规则：
- 共 3~6 条，去重；中英文皆可，按实际需要，**禁止为凑数强行塞至少 3 条英文 filler**。
- 第一条优先「机构 + 姓名 + 角色」完整上下文。
- 可含：姓名+publications / 著作 / 论文；姓名+机构英文名（若合理）。
- 不要编造不存在的机构英文缩写。

人物：{person_name}
机构：{institution}
角色：{role}
主题：{topic}
完整表述：{display_query}
语言偏好：{language}
""".strip()


SEARCH_QUERIES_LITERATURE_PROMPT = """你是资料检索词生成器。

只返回 JSON：
{{
  "refined_queries": ["中文检索词", "英文检索词", "..."]
}}

规则：
- 共 2~6 条；按查询意图覆盖合适的中文或英文来源，不为凑数添加词条。
- 去掉无意义口语，保留人物、机构、事件、时间和学科术语。
- 可排除多义词跑题（不必写 must_exclude，体现在选词上）。

用户原话：{raw_query}
主题：{topic}
语言偏好：{language}
""".strip()
