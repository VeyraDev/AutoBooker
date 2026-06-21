"""模板图示渲染器的 DiagramSpec 元数据。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.figures.intent.taxonomy import canonical_subtype

STYLE_PROFILE = "book_infographic_v1"


@dataclass(frozen=True)
class TemplateLimit:
    chart_type: str
    field: str | None = None
    min: int = 0
    max: int = 0
    fallback: str = ""
    description: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "chart_type": self.chart_type,
            "field": self.field,
            "min": self.min,
            "max": self.max,
            "fallback": self.fallback,
            "description": self.description,
        }


TEMPLATE_LIMITS: dict[str, TemplateLimit] = {
    "horizontal_stage_cards": TemplateLimit(
        chart_type="process_flow",
        field="stages",
        min=2,
        max=4,
        fallback="snake_cards",
        description="2-4 个顺序阶段，每阶段包含标题、要点和可选输入输出。",
    ),
    "snake_cards": TemplateLimit(
        chart_type="process_flow",
        field="steps",
        min=5,
        max=8,
        fallback="grouped_infographic",
        description="5-8 个顺序步骤，两行蛇形阅读路径。",
    ),
    "grouped_infographic": TemplateLimit(
        chart_type="infographic",
        field="cards",
        min=3,
        max=8,
        description="3-8 个并列信息模块。",
    ),
    "vertical_layers": TemplateLimit(
        chart_type="system_architecture",
        field="layers",
        min=2,
        max=4,
        description="2-4 层纵向系统架构。",
    ),
    "shared_resource_three_column": TemplateLimit(
        chart_type="system_architecture",
        description="左侧处理区、中心共享组件、右侧处理区的三栏架构。",
    ),
    "comparison_matrix": TemplateLimit(
        chart_type="comparison",
        field="dimensions",
        min=2,
        max=4,
        description="两对象 x 2-4 个维度的对比矩阵。",
    ),
    "decision_cards": TemplateLimit(
        chart_type="decision_tree",
        field="branches",
        min=2,
        max=3,
        description="根问题 + 2-3 个分支结果卡片。",
    ),
    "horizontal_timeline": TemplateLimit(
        chart_type="timeline",
        field="events",
        min=3,
        max=7,
        description="3-7 个时间节点的横向时间线。",
    ),
    "taxonomy_tree": TemplateLimit(
        chart_type="taxonomy",
        field="groups",
        min=2,
        max=4,
        description="根节点、一级分类和成员的树状分类图。",
    ),

    "comparison_matrix_multi": TemplateLimit(
        chart_type="comparison",
        field="dimensions",
        min=2,
        max=5,
        description="3-4 个对象 x 2-5 个维度的多对象对比矩阵。",
    ),
    "decision_branch_tree": TemplateLimit(
        chart_type="decision_tree",
        field="branches",
        min=2,
        max=4,
        description="条件问题 + 是/否分支 + 结果建议。",
    ),
    "service_topology": TemplateLimit(
        chart_type="system_architecture",
        field="services",
        min=2,
        max=5,
        description="入口模块、多个业务模块和共享基础设施的服务拓扑。",
    ),
    "mechanism_sequence": TemplateLimit(
        chart_type="mechanism",
        field="sections",
        min=3,
        max=6,
        description="3-6 个阶段的机制序列、变量变换或作用链路。",
    ),
    "parallel_stack_architecture": TemplateLimit(
        chart_type="mechanism",
        field="encoder_layers",
        min=2,
        max=6,
        description="左右两组堆叠模块之间交互的通用机制结构。",
    ),
    "hub_spoke_concept": TemplateLimit(
        chart_type="concept",
        field="items",
        min=3,
        max=8,
        description="中心概念 + 周边关系模块。",
    ),
    "mechanism_mapping": TemplateLimit(
        chart_type="mechanism",
        field="sections",
        min=3,
        max=6,
        description="输入、内部机制、中间对象和输出的机制说明图。",
    ),
}

TEMPLATE_IDS = tuple(TEMPLATE_LIMITS.keys())

INFOGRAPHIC_TEMPLATE_SUBTYPES = frozenset(
    {
        "process_flow",
        "system_architecture",
        "mechanism_diagram",
        "comparison_matrix",
        "concept_diagram",
        "infographic",
        "taxonomy_map",
        "decision_tree",
        "timeline_roadmap",
    }
)


def supports_infographic_template(subtype: str) -> bool:
    """Return whether the subtype should use the deterministic template route."""
    return canonical_subtype(subtype) in INFOGRAPHIC_TEMPLATE_SUBTYPES


def limits_as_json() -> dict[str, Any]:
    return {key: value.to_json() for key, value in TEMPLATE_LIMITS.items()}


def default_template_for_subtype(subtype: str) -> str:
    st = canonical_subtype(subtype)
    return {
        "process_flow": "horizontal_stage_cards",
        "system_architecture": "vertical_layers",
        "mechanism_diagram": "mechanism_mapping",
        "comparison_matrix": "comparison_matrix",
        "concept_diagram": "hub_spoke_concept",
        "infographic": "grouped_infographic",
        "taxonomy_map": "taxonomy_tree",
        "decision_tree": "decision_cards",
        "timeline_roadmap": "horizontal_timeline",
    }.get(st, "grouped_infographic")
