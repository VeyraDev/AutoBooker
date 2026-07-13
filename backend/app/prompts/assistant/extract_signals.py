"""Prompt for mixed-source segment extraction (Stage 2)."""

EXTRACT_SEGMENTS_INSTRUCTION = """
分析资料全文，识别其中可能包含的独立用途片段（同一文件可含多种类型）。
只输出 JSON：
{
  "segments": [
    {
      "segment_type": "outline|requirement|manuscript|preface|chapter_draft|bibliography|style_sample|case_material|table_material|figure_material",
      "summary": "50字内说明该片段内容与用途",
      "locator": "大致位置，如「第3-8页」「文首目录段」「参考文献段」",
      "confidence": 0.0到1.0,
      "suggested_usage": "对下游写作的建议，如「严格保留章序」「仅作引用来源」",
      "excerpt": "该片段代表性摘录，最多200字"
    }
  ]
}

规则：
- 混合资料至少尝试拆出 2 种不同类型；单一类型资料返回 1 条即可
- confidence < 0.7 表示需要用户确认
- 不要编造文中不存在的内容
""".strip()
