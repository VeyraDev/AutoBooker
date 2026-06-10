"""Compiler Registry。"""

from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.architecture import ArchitectureCompiler
from app.services.figures.compiler.attention_matrix import AttentionMatrixCompiler
from app.services.figures.compiler.comparison import ComparisonCompiler
from app.services.figures.compiler.decision import DecisionCompiler
from app.services.figures.compiler.flow import FlowCompiler
from app.services.figures.compiler.infographic import InfographicCompiler
from app.services.figures.compiler.mechanism import MechanismCompiler
from app.services.figures.compiler.relationship import RelationshipCompiler
from app.services.figures.compiler.taxonomy import TaxonomyCompiler
from app.services.figures.compiler.swimlane import SwimlaneCompiler
from app.services.figures.compiler.swot import SwotCompiler
from app.services.figures.compiler.timeline import TimelineCompiler
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent

_TYPE_MAP: dict[str, type] = {
    "flow": FlowCompiler,
    "process_flow": FlowCompiler,
    "swimlane": SwimlaneCompiler,
    "business_swimlane": SwimlaneCompiler,
    "architecture": ArchitectureCompiler,
    "system_architecture": ArchitectureCompiler,
    "shared_architecture": ArchitectureCompiler,
    "comparison": ComparisonCompiler,
    "comparison_matrix": ComparisonCompiler,
    "swot": SwotCompiler,
    "attention_matrix": AttentionMatrixCompiler,
    "timeline": TimelineCompiler,
    "timeline_roadmap": TimelineCompiler,
    "taxonomy": TaxonomyCompiler,
    "taxonomy_map": TaxonomyCompiler,
    "org_chart": TaxonomyCompiler,
    "decision_tree": DecisionCompiler,
    "decision": DecisionCompiler,
    "mechanism": MechanismCompiler,
    "mechanism_diagram": MechanismCompiler,
    "concept_map": RelationshipCompiler,
    "relationship_map": RelationshipCompiler,
    "knowledge_graph": RelationshipCompiler,
    "concept_diagram": RelationshipCompiler,
    "concept": RelationshipCompiler,
    "infographic": InfographicCompiler,
    "chapter_summary": InfographicCompiler,
}


def compile_brief(brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
    dtype = canonical_subtype(brief.diagram_type or intent.diagram_subtype or "flow")
    aliases = {
        "flowchart": "flow",
        "business_workflow": "flow",
        "knowledge_graph": "concept_map",
    }
    dtype = aliases.get(dtype, dtype)
    cls = _TYPE_MAP.get(dtype, FlowCompiler)
    compiler = cls()
    native = compiler.compile(brief, intent)
    if not native.structure:
        native.meta["compiler_fallback_blocked"] = True
    return native


def project_native_to_graph(native: NativeIR, intent: DiagramIntent):
    from app.services.figures.compiler.projector import native_ir_to_graph

    return native_ir_to_graph(native, intent)
