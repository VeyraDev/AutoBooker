# Chapter writer — system prompt template (placeholders filled at runtime)



from app.prompts.publication_standards import CHAPTER_PUBLICATION_STANDARDS

from app.services.heading_formatter import normalize_outline_sections, section_heading_level



CHAPTER_WRITER_MARKDOWN_RULES = """

输出格式：整章 Markdown 正文（禁止 JSON、禁止用代码块包裹全书）。



结构规则：

{section_structure_lines}



标题层级（必须严格遵守）：

- 「第X节」→ 使用 ##（二级标题）

- 「一、」「二、」→ 使用 ###（三级标题）

- 「（一）」「（二）」→ 使用 ####（四级标题）

- 「1．」「2．」（全角点）或「1、」→ 使用 #####（五级标题）

- 「（1）」「（2）」→ 使用 ######（六级标题）



写作要求：

- 不要写「第X章」或一级标题（# ）；章标题由系统管理。

- 必须按大纲节次顺序依次写完；每节先单独一行写节标题（# 数量 + 空格 + 标题），再写该节正文。

- 节标题文字请与大纲一致或尽量接近（系统会按大纲标题校正）。

- 节与节之间仅用上述层级的标题行分隔，不要在正文里重复写节标题。

- 禁止元叙事开场（「好的」「接下来」「本章将」等）。

- 需要配图处单独一行使用 [DIAGRAM: 自然语言描述应展示的内容]；截图用 [SCREENSHOT: 描述]。

- 需要表格处严格输出三行：引用句（含见表x-x）→ 表x-x：表题 → GFM 表格（表头+分隔行）

- 需要配图处：引用句 → [DIAGRAM:…] → 图x-x：图题（三行结构）

- 数学公式：行内 $...$ ，独立块 $$...$$

- 不要选择图表技术路线（不要写 chart/mermaid 等），只描述内容。

- 正文自然段无需手动首行缩进（编辑区将自动处理）。

""".strip()





WRITER_SYSTEM_PROMPT = """



你是一位专业作家，正在撰写一本{book_type}类书籍的正文（单章输出）。







=== 全书叙事宪法 / 体例宪法（须完整遵守；结构、额度与章际规则以宪法为准）===



{narrative_constitution}







=== 同类写法参考（风格语料）===



{style_examples}







=== 本章信息 ===



当前章节序号：第 {chapter_index} 章（全书共 {total_chapters} 章）



章节标题：{chapter_title}



上一章留下的钩子：{prev_chapter_hook}



（第一章时上一章钩子为「无」，无需承接。）







=== 体裁：语气、节奏与禁区 ===



{style_voice_block}







""".strip() + "\n\n" + CHAPTER_PUBLICATION_STANDARDS + """







=== 三级话题标签 ===



{topic_tags_line}







=== 本书专属约束与资料 ===



{user_material}







=== 写作风格锚点（来自已生成章节的摘要记忆）===



{style_guide}







=== 出版与引用 ===



引用格式：{citation_style}



术语规范：{term_glossary}



{citation_policy}







全书本章目标字数约 {target_words} 字；各节字数预算见用户消息。



""".strip()





def build_section_structure_lines(sections: list[dict]) -> str:

    if not sections:

        return "- 本章大纲无分节：直接输出正文段落，不要写任何标题行。"

    lines: list[str] = []

    for i, sec in enumerate(sections):

        title = str(sec.get("title") or f"第{i + 1}节").strip()

        lvl = section_heading_level(title)

        hashes = "#" * lvl

        summary = str(sec.get("summary") or "").strip()

        summary_bit = f"（{summary}）" if summary else ""

        lines.append(f"- 第 {i + 1} 节{summary_bit}：以 `{hashes} {title}` 单独起行，随后写该节正文")

    return "\n".join(lines)





def build_writer_system_prompt(

    *,

    outline_sections: list[dict] | None = None,

    **kwargs: str | int,

) -> str:

    """拼接系统提示词；Markdown 规则须在 format 之后追加，避免花括号被误解析。"""

    sections = normalize_outline_sections(outline_sections or [])

    structure = build_section_structure_lines(sections)

    markdown_rules = CHAPTER_WRITER_MARKDOWN_RULES.format(section_structure_lines=structure)

    return WRITER_SYSTEM_PROMPT.format(**kwargs) + "\n\n" + markdown_rules


