from __future__ import annotations

from app.services.assistant.context import AssistantContext


def build_execution_prompt(intent: dict, ctx: AssistantContext) -> tuple[str, str, dict]:
    i = intent.get("intent", "rewrite")
    params = intent.get("extracted_params") or {}

    if i == "polish":
        system = f"""你是一位{ctx.style_type}类图书的文字编辑。
润色方向：{params.get('direction', '保持原风格，提升流畅度')}
全书风格基调：{ctx.style_type}
不要改变原文的核心意思和技术内容。"""
        user = f"请润色以下文字：\n\n{ctx.selected_text or ctx.cursor_paragraph}"

    elif i == "rewrite":
        system = f"你是一位{ctx.style_type}类图书的文字编辑。"
        user = f"""改写要求：{params.get('instruction', ctx.user_text)}

原文：
{ctx.selected_text or ctx.cursor_paragraph}

改写后直接输出，不要解释。"""

    elif i == "expand":
        system = "你是专业中文编辑，只输出扩写结果。"
        user = f"请扩写以下文字：\n\n{ctx.selected_text or ctx.cursor_paragraph}"

    elif i == "condense":
        system = "你是专业中文编辑，只输出缩写结果。"
        user = f"请缩写以下文字：\n\n{ctx.selected_text or ctx.cursor_paragraph}"

    elif i == "style_adjust":
        system = f"你是{ctx.style_type}类图书编辑，调整文风但保留技术内容。"
        direction = params.get("direction", ctx.user_text or "更正式")
        user = f"风格调整方向：{direction}\n\n{ctx.selected_text or ctx.cursor_paragraph}"

    elif i == "term_check":
        system = "你是术语编辑，检查术语一致性并给出修改建议，直接输出修订后全文。"
        user = f"全书风格：{ctx.style_type}\n\n{ctx.selected_text or ctx.cursor_paragraph}"

    elif i in ("gen_flowchart", "regen_figure"):
        description = ctx.figure_annotation or ctx.selected_text or ctx.user_text
        system = "将流程描述转换为Graphviz DOT代码，只返回代码。"
        user = f"""书型：{ctx.book_type}
配色风格：专业技术书籍，蓝白配色
流程描述：{description}"""
        params = {**params, "_pipeline": "flowchart", "_description": description}

    elif i == "gen_chart":
        description = ctx.figure_annotation or ctx.user_text
        system = "将图表描述解析为matplotlib绘图规格JSON，只返回JSON。"
        user = f"图表描述：{description}"
        params = {**params, "_pipeline": "chart", "_description": description}

    elif i == "gen_figure":
        description = ctx.figure_annotation or ctx.user_text
        style_prefix = {
            "textbook": "Academic technical illustration",
            "popular_science": "Modern infographic style",
            "practical_guide": "Step-by-step technical diagram",
        }.get(ctx.style_type, "Professional publishing illustration")
        system = "生成图像prompt，只返回prompt文本。"
        user = f"风格：{style_prefix}\n内容：{description}"
        params = {
            **params,
            "_pipeline": "figure",
            "_description": description,
            "sub_kind": params.get("sub_kind", "figure"),
        }

    else:
        system = "你是一位专业的图书写作助手。"
        user = ctx.user_text

    return system, user, params
