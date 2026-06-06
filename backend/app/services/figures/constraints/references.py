"""references 展开为 relations。"""

from __future__ import annotations

from app.services.figures.semantic.schema import SemanticIR, SemanticReference


def expand_references(ir: SemanticIR) -> list[dict]:
    """将 references 展开为 relations 列表。"""
    relations: list[dict] = []
    name_to_id = ir.object_by_name()
    service_ids = [o.id for o in ir.objects if o.kind in {"service", "process", "module", "gateway"}]

    for ref in ir.references:
        relations.extend(_expand_one(ref, ir, name_to_id, service_ids))
    return relations


def _expand_one(
    ref: SemanticReference,
    ir: SemanticIR,
    name_to_id: dict[str, str],
    service_ids: list[str],
) -> list[dict]:
    out: list[dict] = []
    valid_ids = ir.object_ids()
    src = ref.source if ref.source in valid_ids else name_to_id.get(ref.source, ref.source)
    if ref.type == "ordinal_selection":
        targets = _ordinal_targets(ref, ir, service_ids)
        for tgt in targets:
            if src and tgt and src != tgt:
                out.append({
                    "from": src,
                    "to": tgt,
                    "verb": ref.action or "连接",
                    "label": ref.label,
                    "async": False,
                })
    elif ref.type == "all_of_type":
        kind = ref.target_set or "service"
        targets = [o.id for o in ir.objects if o.kind == kind and o.id != src]
        for tgt in targets:
            out.append({"from": src, "to": tgt, "verb": ref.action or "连接", "label": ref.label, "async": False})
    elif ref.type == "shared_between":
        members = [name_to_id.get(m, m) for m in ref.target_set.split(",") if m.strip()]
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                out.append({"from": a, "to": b, "verb": "共享", "label": ref.label, "async": False})
    return out


def _ordinal_targets(ref: SemanticReference, ir: SemanticIR, service_ids: list[str]) -> list[str]:
    pool = service_ids
    if ref.target_set == "services":
        pool = [o.id for o in ir.objects if o.kind == "service"]
    elif ref.target_set:
        pool = [o.id for o in ir.objects if o.kind == ref.target_set or o.name in ref.target_set]
    if not pool:
        pool = [o.id for o in ir.objects if o.kind != "gateway"]
    start = max(0, (ref.range_start or 1) - 1)
    end = ref.range_end or len(pool)
    if end <= 0:
        end = 3
    return pool[start:end]
