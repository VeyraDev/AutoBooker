"""Canvas guidance and provider size selection for the Image API route."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanvasProfile:
    key: str
    aspect_label: str
    orientation: str
    guidance: str
    openai_gpt_size: str
    openai_dalle3_size: str
    wanx_size: str


SQUARE_CANVAS = CanvasProfile(
    key="square",
    aspect_label="1:1 方形画布",
    orientation="居中或轻微分区",
    guidance="适合少量模块、概念关系或场景插图；四周保留清晰安全边距，避免贴边。",
    openai_gpt_size="1024x1024",
    openai_dalle3_size="1024x1024",
    wanx_size="1024*1024",
)

LANDSCAPE_CANVAS = CanvasProfile(
    key="landscape",
    aspect_label="横向宽画布，约 3:2 或 16:9",
    orientation="从左到右阅读，必要时使用两行蛇形折返",
    guidance="适合流程图、系统架构图、时间线和横向对比；所有节点、箭头和文字必须落在画布安全边距内，不得把首尾节点画到画布外。",
    openai_gpt_size="1536x1024",
    openai_dalle3_size="1792x1024",
    wanx_size="1280*720",
)

PORTRAIT_CANVAS = CanvasProfile(
    key="portrait",
    aspect_label="纵向画布，约 2:3 或 9:16",
    orientation="自上而下阅读，层级逐级展开",
    guidance="适合决策树、层级分类和纵向分层说明；上下左右保留安全边距，底部节点不得被裁切。",
    openai_gpt_size="1024x1536",
    openai_dalle3_size="1024x1792",
    wanx_size="720*1280",
)


_SUBTYPE_CANVAS: dict[str, CanvasProfile] = {
    "process_flow": LANDSCAPE_CANVAS,
    "system_architecture": LANDSCAPE_CANVAS,
    "mechanism_diagram": LANDSCAPE_CANVAS,
    "comparison_matrix": LANDSCAPE_CANVAS,
    "timeline_roadmap": LANDSCAPE_CANVAS,
    "decision_tree": PORTRAIT_CANVAS,
    "taxonomy_map": PORTRAIT_CANVAS,
    "concept_diagram": SQUARE_CANVAS,
    "infographic": LANDSCAPE_CANVAS,
    "scene_illustration": SQUARE_CANVAS,
}


def canvas_profile_for_subtype(subtype: str) -> CanvasProfile:
    return _SUBTYPE_CANVAS.get(str(subtype or "").strip().lower(), SQUARE_CANVAS)


def canvas_guidance_for_subtype(
    subtype: str,
    *,
    user_input: str = "",
    layout_risks: str = "",
) -> str:
    profile = canvas_profile_for_subtype(subtype)
    st = str(subtype or "").strip().lower()
    extra = ""
    if st == "process_flow":
        extra = (
            "流程步骤较多或单行会拥挤时，优先使用两行蛇形折返布局；"
            "短流程可横向一行排列，但首尾节点必须完整可见。"
        )
    elif st == "system_architecture":
        extra = (
            "架构图优先使用横向分区、上下分层或中心共享组件布局；"
            "不要把架构模块压成窄小流程节点。"
        )
    elif st == "timeline_roadmap":
        extra = "时间线主轴横向贯穿画面，事件说明上下错落，避免两端年份或事件被裁切。"
    elif st == "infographic":
        extra = (
            "信息图优先使用横向卡片网格或分组信息架构；章节总结、知识总结或模块超过 3 个时，"
            "使用 2×3、3×2 或 2×4 布局，避免退化成松散图标圆点。"
        )
    elif st in {"decision_tree", "taxonomy_map"}:
        extra = "层级向下展开时要预留底部空间，叶子节点不得贴近画布边缘。"

    if layout_risks:
        extra = f"{extra} 布局风险：{layout_risks}".strip()
    if user_input and len(user_input) > 160:
        extra = f"{extra} 内容较长时优先增加画布留白、换行和分组，不要缩小文字。".strip()

    return "\n".join(
        [
            f"画布比例：{profile.aspect_label}",
            f"画布方向：{profile.orientation}",
            "安全边距：四周至少保留 8% 到 12% 空白区域；任何文字、节点、箭头、图例不得贴边或被裁切。",
            f"布局策略：{profile.guidance}",
            f"补充要求：{extra or '无'}",
        ]
    )


def openai_size_for_canvas(
    model: str,
    *,
    subtype: str,
    configured_size: str = "",
) -> str:
    raw = str(configured_size or "").strip()
    if raw and raw.lower() != "1024x1024":
        return raw

    m = str(model or "").strip().lower()
    profile = canvas_profile_for_subtype(subtype)
    if m.startswith("dall-e-2"):
        return "1024x1024"
    if m.startswith("dall-e-3"):
        return profile.openai_dalle3_size
    return profile.openai_gpt_size


def wanx_size_for_canvas(*, subtype: str) -> str:
    return canvas_profile_for_subtype(subtype).wanx_size
