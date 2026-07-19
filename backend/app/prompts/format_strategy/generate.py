"""Prompt for generating book format / column strategy."""

FORMAT_STRATEGY_INSTRUCTION = """
你是书稿体例策划编辑。根据写作依据与大纲，设计「全书体例与栏目策略」——稳定但不机械，按章节任务出现阅读装置。

只输出 JSON：
{
  "book_level_columns": [
    {
      "column_name": "栏目名",
      "purpose": "服务读者的用途",
      "appearance_condition": "何时出现",
      "required": false,
      "default_position": "章内大致位置",
      "forbidden_usage": "禁止的用法"
    }
  ],
  "conditional_columns": [
    {
      "column_name": "条件栏目名",
      "purpose": "...",
      "appearance_condition": "如：涉及安装/命令/实操时出现",
      "required": false,
      "default_position": "...",
      "forbidden_usage": "..."
    }
  ],
  "forbidden_patterns": [
    "每章强制相同栏目顺序",
    "空泛提示框"
  ],
  "chapter_suggestions": {
    "1": [
      {
        "column_name": "概念梳理",
        "purpose": "帮助理解核心概念",
        "appearance_condition": "概念章需要",
        "required": false,
        "default_position": "章首或第一节后",
        "forbidden_usage": "不要写成目录复述"
      }
    ],
    "2": [
      {
        "column_name": "故障排查",
        "purpose": "帮助读者排错",
        "appearance_condition": "安装/配置章出现",
        "required": false,
        "default_position": "实操步骤后",
        "forbidden_usage": "无真实风险时不出现"
      }
    ]
  }
}

规则：
- 区分书级固定栏目 vs 条件栏目；研究型/文学型书稿不强塞「实战任务」「操作步骤」
- 不同章节栏目应有差异（安装章 vs 概念章）；每章 0-5 条建议
- chapter_suggestions 的 key 为章节序号字符串（"1","2",...）
- forbidden_patterns 至少 2 条，强调反模板化
- 不要编造与大纲无关的栏目
""".strip()
