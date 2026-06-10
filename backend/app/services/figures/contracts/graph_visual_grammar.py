"""Graph visual grammar selection and hard semantic requirements."""

from __future__ import annotations

from app.services.figures.intent.taxonomy import canonical_subtype

GRAPH_GRAMMAR_PROCESS_FLOW = "process_flow"
GRAPH_GRAMMAR_ARCHITECTURE = "architecture"
GRAPH_GRAMMAR_MECHANISM = "mechanism"
GRAPH_GRAMMAR_RADIAL_CONCEPT = "radial_concept"
GRAPH_GRAMMAR_NETWORK = "network"
GRAPH_GRAMMAR_DECISION_TREE = "decision_tree"
GRAPH_GRAMMAR_GENERIC = "generic"

GRAPH_VISUAL_GRAMMARS = frozenset(
    {
        GRAPH_GRAMMAR_PROCESS_FLOW,
        GRAPH_GRAMMAR_ARCHITECTURE,
        GRAPH_GRAMMAR_MECHANISM,
        GRAPH_GRAMMAR_RADIAL_CONCEPT,
        GRAPH_GRAMMAR_NETWORK,
        GRAPH_GRAMMAR_DECISION_TREE,
        GRAPH_GRAMMAR_GENERIC,
    }
)

GRAMMAR_TO_RENDER_PROFILE = {
    GRAPH_GRAMMAR_PROCESS_FLOW: "svg.flow",
    GRAPH_GRAMMAR_ARCHITECTURE: "svg.architecture",
    GRAPH_GRAMMAR_MECHANISM: "svg.mechanism",
    GRAPH_GRAMMAR_RADIAL_CONCEPT: "svg.radial",
    GRAPH_GRAMMAR_NETWORK: "svg.network",
    GRAPH_GRAMMAR_DECISION_TREE: "svg.decision",
}

MANDATORY_SEMANTICS: dict[str, list[str]] = {
    GRAPH_GRAMMAR_PROCESS_FLOW: [
        "main_spine",
        "start_end_nodes",
        "decision_diamond",
        "branch_labels",
        "loop_optional_parallel",
    ],
    GRAPH_GRAMMAR_ARCHITECTURE: [
        "zones_layers_groups",
        "component_cards",
        "data_store_queue_shapes",
        "orthogonal_cross_layer_edges",
        "layer_titles",
    ],
    GRAPH_GRAMMAR_MECHANISM: [
        "stage_bands",
        "input_operation_output_roles",
        "transformation_arrows",
        "feedback_lane",
        "state_tensor_operation_shapes",
    ],
    GRAPH_GRAMMAR_RADIAL_CONCEPT: [
        "center_node",
        "satellite_nodes",
        "radial_links",
        "relationship_labels",
        "non_linear_layout",
    ],
    GRAPH_GRAMMAR_NETWORK: [
        "typed_clusters",
        "hub_emphasis",
        "relationship_edge_labels",
        "network_layout",
        "node_type_encoding",
    ],
    GRAPH_GRAMMAR_DECISION_TREE: [
        "top_down_tree",
        "condition_diamonds",
        "branch_labels",
        "yes_no_paths",
        "outcome_leaf_nodes",
    ],
    GRAPH_GRAMMAR_GENERIC: ["nodes", "edges"],
}


def graph_visual_grammar_for_subtype(subtype: str) -> str:
    """Map a canonical diagram subtype to its graph visual grammar."""
    st = canonical_subtype(subtype)
    if st in {"process_flow", "business_workflow"}:
        return GRAPH_GRAMMAR_PROCESS_FLOW
    if st in {"system_architecture", "shared_architecture", "microservice_architecture"}:
        return GRAPH_GRAMMAR_ARCHITECTURE
    if st == "mechanism_diagram":
        return GRAPH_GRAMMAR_MECHANISM
    if st in {"concept_diagram"}:
        return GRAPH_GRAMMAR_RADIAL_CONCEPT
    if st == "knowledge_graph":
        return GRAPH_GRAMMAR_NETWORK
    if st in {"decision_tree", "decision_flow"}:
        return GRAPH_GRAMMAR_DECISION_TREE
    return GRAPH_GRAMMAR_GENERIC


def mandatory_semantics_for_grammar(grammar: str) -> list[str]:
    """Return hard renderer semantics for a graph grammar."""
    key = grammar if grammar in MANDATORY_SEMANTICS else GRAPH_GRAMMAR_GENERIC
    return list(MANDATORY_SEMANTICS[key])


def render_profile_for_graph_grammar(grammar: str) -> str | None:
    """Return the dedicated SVG profile for a graph grammar, if any."""
    return GRAMMAR_TO_RENDER_PROFILE.get(grammar)
