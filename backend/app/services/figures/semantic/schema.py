"""Semantic IR 数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SemanticObject:
    id: str
    name: str
    kind: str = "process"
    importance: int = 2
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "importance": self.importance,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticObject:
        return cls(
            id=str(data.get("id") or ""),
            name=str(data.get("name") or ""),
            kind=str(data.get("kind") or data.get("type") or "process"),
            importance=int(data.get("importance") or 2),
            tags=[str(t) for t in (data.get("tags") or [])],
        )


@dataclass
class SemanticEvent:
    type: str
    sender: str = ""
    receiver: str = ""
    channel: str = ""
    label: str = ""
    edge_style: str = "solid"
    async_flag: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "sender": self.sender,
            "receiver": self.receiver,
            "channel": self.channel,
            "label": self.label,
            "edge_style": self.edge_style,
            "async": self.async_flag,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticEvent:
        return cls(
            type=str(data.get("type") or "sync_call"),
            sender=str(data.get("sender") or data.get("from") or ""),
            receiver=str(data.get("receiver") or data.get("to") or ""),
            channel=str(data.get("channel") or ""),
            label=str(data.get("label") or ""),
            edge_style=str(data.get("edge_style") or ("dashed" if data.get("async") else "solid")),
            async_flag=bool(data.get("async", False)),
        )


@dataclass
class SemanticReference:
    type: str
    source: str = ""
    target_set: str = ""
    range_start: int = 0
    range_end: int = 0
    action: str = "connect"
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": self.type,
            "source": self.source,
            "target_set": self.target_set,
            "action": self.action,
        }
        if self.range_start or self.range_end:
            out["range"] = [self.range_start, self.range_end]
        if self.label:
            out["label"] = self.label
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticReference:
        rng = data.get("range") or []
        r0, r1 = 0, 0
        if isinstance(rng, list) and len(rng) >= 2:
            r0, r1 = int(rng[0]), int(rng[1])
        return cls(
            type=str(data.get("type") or "ordinal_selection"),
            source=str(data.get("source") or ""),
            target_set=str(data.get("target_set") or data.get("targets") or ""),
            range_start=r0,
            range_end=r1,
            action=str(data.get("action") or "connect"),
            label=str(data.get("label") or ""),
        )


@dataclass
class SemanticIR:
    diagram_type: str = "flowchart"
    title: str = ""
    domain: str = ""
    objects: list[SemanticObject] = field(default_factory=list)
    events: list[SemanticEvent] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    references: list[SemanticReference] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    groups: list[dict[str, Any]] = field(default_factory=list)
    layout_hints: list[str] = field(default_factory=list)
    style_hints: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagram_type": self.diagram_type,
            "title": self.title,
            "domain": self.domain,
            "objects": [o.to_dict() for o in self.objects],
            "events": [e.to_dict() for e in self.events],
            "relations": list(self.relations),
            "references": [r.to_dict() for r in self.references],
            "constraints": list(self.constraints),
            "groups": list(self.groups),
            "layout_hints": list(self.layout_hints),
            "style_hints": list(self.style_hints),
            "unknowns": list(self.unknowns),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticIR:
        objs = [SemanticObject.from_dict(o) for o in (data.get("objects") or data.get("entities") or []) if isinstance(o, dict)]
        evts = [SemanticEvent.from_dict(e) for e in (data.get("events") or []) if isinstance(e, dict)]
        refs = [SemanticReference.from_dict(r) for r in (data.get("references") or []) if isinstance(r, dict)]
        return cls(
            diagram_type=str(data.get("diagram_type") or "flowchart"),
            title=str(data.get("title") or ""),
            domain=str(data.get("domain") or ""),
            objects=objs,
            events=evts,
            relations=[dict(r) for r in (data.get("relations") or []) if isinstance(r, dict)],
            references=refs,
            constraints=[dict(c) for c in (data.get("constraints") or []) if isinstance(c, dict)],
            groups=[dict(g) for g in (data.get("groups") or []) if isinstance(g, dict)],
            layout_hints=[str(x) for x in (data.get("layout_hints") or [])],
            style_hints=[str(x) for x in (data.get("style_hints") or [])],
            unknowns=[str(x) for x in (data.get("unknowns") or data.get("notes") or [])],
        )

    def object_ids(self) -> set[str]:
        return {o.id for o in self.objects if o.id}

    def object_by_name(self) -> dict[str, str]:
        return {o.name: o.id for o in self.objects}
