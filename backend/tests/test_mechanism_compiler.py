from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.mechanism import MechanismCompiler
from app.services.figures.schemas.diagram import DiagramIntent


def test_mechanism_compiler_accepts_chinese_interaction_fields():
    brief = VisualBrief(
        diagram_type="mechanism_diagram",
        title="甲机制",
        content_brief={
            "作用关系": [
                {"来源": "甲", "目标": "乙", "传递内容": "信号", "作用": "激活"},
                {"来源": "乙", "目标": "甲", "传递内容": "反馈", "作用": "反馈"},
            ]
        },
    )

    native = MechanismCompiler().compile(brief, DiagramIntent("knowledge", "mechanism_diagram", title="甲机制"))
    structure = native.structure

    assert structure["interactions"][0] == {"from": "甲", "to": "乙", "what": "信号", "effect": "activate"}
    assert structure["causal_links"][0]["polarity"] == "positive"
    assert structure["feedbacks"][0] == {"from": "乙", "to": "甲", "meaning": "反馈"}
