"""从文本规则推断通用图结构（LLM 不可用时的兜底）。"""

from __future__ import annotations

import re
from typing import Any


def _split_tags(text: str) -> list[str]:
    parts = re.split(r"[、,，;；/\s]+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()][:8]


def _default_tags(choice: str) -> list[str]:
    key = re.sub(r"^选择\s*", "", (choice or "").strip(), flags=re.I).lower()
    defaults = {
        "vllm": ["高吞吐", "低延迟", "显存优化"],
        "langchain": ["模块化", "链式调用", "工具集成"],
        "hermes": ["快速上手", "开箱即用", "开发效率"],
    }
    for name, tags in defaults.items():
        if name in key:
            return tags
    return []


def infer_structured_spec(text: str) -> dict[str, Any] | None:
    """尽力从自然语言推断 nodes/edges；层数随描述变化，不固定模板。"""
    t = (text or "").strip()
    if not t:
        return None

    root = "你的主要需求是什么？"
    rm = re.search(r"根节点[「\"']?([^」\"'\n，。]+)", t)
    if rm:
        root = rm.group(1).strip()
    else:
        m = re.search(r"[「\"']([^」\"']{2,40})[」\"']", t)
        if m and ("根" in t or "决策" in t):
            root = m.group(1).strip()

    branches: list[dict[str, str]] = []
    for part in re.split(r"[；;\n]", t):
        if "→" not in part and "->" not in part:
            continue
        segs = [s.strip() for s in re.split(r"→|->", part) if s.strip()]
        if len(segs) < 2:
            continue
        cond = re.sub(r"^\d+[.、)\s]+", "", segs[0]).strip("「」\"'")
        choice = re.sub(r"^选择\s*", "", segs[1].strip("「」\"'"), flags=re.I)
        extra = segs[2].strip() if len(segs) > 2 else ""
        branches.append({"condition": cond, "choice": choice, "extra": extra})

    if not branches:
        for m in re.finditer(
            r"[「\"']?([^「」\"'\n]{2,30})[」\"']?\s*→\s*[「\"']?(?:选择\s*)?([^「」\"'\n：:]+)[」\"']?",
            t,
        ):
            branches.append({"condition": m.group(1), "choice": m.group(2), "extra": ""})

    if not branches:
        return None

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    nodes.append({"id": "root", "label": root, "shape": "diamond", "level": 0, "column": 0})

    want_tags = bool(re.search(r"优势|关键词|标签|特点", t))
    max_level = 2 if not want_tags else 3

    for i, br in enumerate(branches[:4]):
        cid = f"c{i}"
        nid = f"n{i}"
        nodes.append(
            {
                "id": cid,
                "label": br["condition"][:36],
                "shape": "box",
                "level": 1,
                "column": i,
            }
        )
        nodes.append(
            {
                "id": nid,
                "label": f"选择 {br['choice']}"[:28],
                "shape": "rounded",
                "level": 2,
                "column": i,
            }
        )
        edges.extend([
            {"from": "root", "to": cid},
            {"from": cid, "to": nid},
        ])

        if max_level >= 3:
            tags = _split_tags(br.get("extra", "")) or _default_tags(br["choice"])
            for j, tag in enumerate(tags[:6]):
                tid = f"t{i}_{j}"
                nodes.append(
                    {
                        "id": tid,
                        "label": tag[:10],
                        "shape": "tag",
                        "level": 3,
                        "column": i,
                        "parent": nid,
                    }
                )
                edges.append({"from": nid, "to": tid})

    return {
        "layout": "TB",
        "structure_summary": f"{max_level + 1}层决策结构",
        "nodes": nodes,
        "edges": edges,
    }


def has_structured_graph(render_spec: dict[str, Any] | None) -> bool:
    if not isinstance(render_spec, dict):
        return False
    nodes = render_spec.get("nodes") or []
    if len(nodes) < 2:
        return False
    ok = 0
    for n in nodes:
        if isinstance(n, dict) and n.get("id") and str(n.get("label", "")).strip():
            ok += 1
    return ok >= 2
