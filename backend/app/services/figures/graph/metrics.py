"""图特征度量。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.services.figures.graph.schema import GraphIR


def compute_graph_metrics(graph: GraphIR) -> dict[str, Any]:
    nodes = graph.nodes
    edges = graph.edges
    node_ids = {n.id for n in nodes}
    out_deg: dict[str, int] = defaultdict(int)
    in_deg: dict[str, int] = defaultdict(int)
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e.source in node_ids and e.target in node_ids:
            out_deg[e.source] += 1
            in_deg[e.target] += 1
            adj[e.source].append(e.target)

    roots = [n.id for n in nodes if in_deg.get(n.id, 0) == 0]
    leaves = [n.id for n in nodes if out_deg.get(n.id, 0) == 0]
    hub_nodes = [nid for nid, d in out_deg.items() if d >= 3]

    depth = _max_depth(roots or [nodes[0].id], adj) if nodes else 0
    is_linear = _is_linear_chain(nodes, edges)
    has_cycle = _has_cycle(node_ids, adj)
    has_decision = any(n.kind == "decision" for n in nodes)
    has_groups = bool(graph.groups)

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "max_depth": depth,
        "hub_nodes": hub_nodes,
        "is_linear_chain": is_linear,
        "has_cycle": has_cycle,
        "has_decision": has_decision,
        "has_groups": has_groups,
        "root_count": len(roots),
        "leaf_count": len(leaves),
        "max_out_degree": max(out_deg.values()) if out_deg else 0,
    }


def _max_depth(starts: list[str], adj: dict[str, list[str]]) -> int:
    best = 0
    for s in starts:
        stack: list[tuple[str, int, frozenset[str]]] = [(s, 1, frozenset({s}))]
        while stack:
            nid, d, seen = stack.pop()
            best = max(best, d)
            for nxt in adj.get(nid, []):
                if nxt in seen:
                    continue
                stack.append((nxt, d + 1, seen | frozenset({nxt})))
    return best


def _is_linear_chain(nodes, edges) -> bool:
    if len(nodes) <= 1:
        return True
    out_counts = defaultdict(int)
    in_counts = defaultdict(int)
    for e in edges:
        out_counts[e.source] += 1
        in_counts[e.target] += 1
    for n in nodes:
        if out_counts[n.id] > 1 or in_counts[n.id] > 1:
            return False
    return len(edges) >= len(nodes) - 1


def _has_cycle(node_ids: set[str], adj: dict[str, list[str]]) -> bool:
    visited: set[str] = set()
    stack: set[str] = set()

    def dfs(nid: str) -> bool:
        visited.add(nid)
        stack.add(nid)
        for nxt in adj.get(nid, []):
            if nxt not in visited:
                if dfs(nxt):
                    return True
            elif nxt in stack:
                return True
        stack.remove(nid)
        return False

    for nid in node_ids:
        if nid not in visited and dfs(nid):
            return True
    return False
