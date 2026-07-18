"""Person-works search intent — general compound-query parsing (no place-name blacklist)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_HONORIFIC_RE = re.compile(
    r"(教授|副教授|讲师|研究员|院士|博士|老师|先生|女士|主任|院长|学者|工程师)$"
)
# Institution-like spans: prefer longest match from the left of a compound query
_INSTITUTION_RE = re.compile(
    r"^(.+?(?:大学|学院|研究院|研究所|实验室|医院|中心|公司|集团|报社|出版社|科学院))"
)


@dataclass
class PersonSearchIntent:
    search_type: str = "person_works"
    person_name: str = ""
    person_name_raw: str = ""
    institution: str | None = None
    role: str | None = None
    topic: str | None = None
    language: list[str] = field(default_factory=lambda: ["zh", "en"])
    source_types: list[str] = field(default_factory=lambda: ["academic", "official_institution"])
    require_author_match: bool = True
    # Full contextual query preferred for encyclopedia / web (keeps affiliation+role)
    display_query: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_type": self.search_type,
            "person_name": self.person_name,
            "person_name_raw": self.person_name_raw,
            "institution": self.institution,
            "role": self.role,
            "topic": self.topic,
            "language": list(self.language),
            "source_types": list(self.source_types),
            "require_author_match": self.require_author_match,
            "display_query": self.display_query,
        }


def _strip_honorific(name: str) -> tuple[str, str | None]:
    raw = name.strip()
    m = _HONORIFIC_RE.search(raw)
    if not m:
        return raw, None
    role = m.group(1)
    cleaned = _HONORIFIC_RE.sub("", raw).strip()
    return cleaned or raw, role


def parse_compound_person_query(raw: str) -> tuple[str, str | None, str | None]:
    """Parse phrases like「清华大学沈阳教授」「MIT Alice Smith professor」into parts.

    Generic heuristics only — no per-city / per-person hardcodes.
    """
    text = re.sub(r"\s+", " ", (raw or "").strip())
    if not text:
        return "", None, None

    institution: str | None = None
    role: str | None = None
    rest = text

    # Role at end (Chinese honorific / English title)
    role_m = _HONORIFIC_RE.search(rest)
    if role_m and role_m.end() == len(rest):
        role = role_m.group(1)
        rest = rest[: role_m.start()].strip()
    else:
        en_role = re.search(r"\b(professor|prof\.?|dr\.?|phd)\b\s*$", rest, re.I)
        if en_role:
            role = en_role.group(1)
            rest = rest[: en_role.start()].strip()

    # Institution at start
    inst_m = _INSTITUTION_RE.match(rest)
    if inst_m:
        institution = inst_m.group(1).strip()
        rest = rest[inst_m.end() :].strip(" ，,·、")
    else:
        # English: "Tsinghua University Shen Yang"
        en_inst = re.match(
            r"^(.+?\b(?:University|College|Institute|Lab|Hospital|Academy)\b)\s+",
            rest,
            re.I,
        )
        if en_inst:
            institution = en_inst.group(1).strip()
            rest = rest[en_inst.end() :].strip()

    person = rest.strip() or text
    person, inferred_role = _strip_honorific(person)
    if not role and inferred_role:
        role = inferred_role
    return person, institution, role


def build_person_search_intent(
    person_name: str,
    *,
    institution: str | None = None,
    topic: str | None = None,
    role: str | None = None,
    query: str | None = None,
) -> PersonSearchIntent:
    """Build intent from structured fields and/or a raw compound query.

    If institution/role missing, try to parse them out of person_name or query.
    """
    raw = (query or person_name or "").strip()
    name_in = (person_name or "").strip() or raw
    inst_in = (institution or "").strip() or None
    role_in = (role or "").strip() or None
    top = (topic or "").strip() or None

    # Prefer structured fields; fill gaps by parsing the richest raw string
    parse_src = raw if (not inst_in or not role_in or len(name_in) > 8) else name_in
    parsed_name, parsed_inst, parsed_role = parse_compound_person_query(parse_src)

    person = name_in
    # If caller stuffed a compound into person_name, prefer parsed person token
    if parsed_inst or parsed_role:
        if not inst_in and parsed_inst:
            person = parsed_name or person
        elif len(name_in) >= 4 and parsed_name and parsed_name != name_in:
            # name_in may still be compound
            if parsed_inst and parsed_inst in name_in:
                person = parsed_name
    if not inst_in:
        inst_in = parsed_inst
    if not role_in:
        role_in = parsed_role
    person, maybe_role = _strip_honorific(person)
    if not role_in and maybe_role:
        role_in = maybe_role

    display_parts = [p for p in (inst_in, person, role_in) if p]
    display_query = "".join(display_parts) if all(
        not re.search(r"[A-Za-z]", p or "") for p in display_parts
    ) else " ".join(display_parts)

    return PersonSearchIntent(
        person_name=person or name_in,
        person_name_raw=raw or name_in,
        institution=inst_in,
        role=role_in,
        topic=top,
        display_query=display_query or person or name_in,
    )


def build_person_queries(intent: PersonSearchIntent) -> list[str]:
    """Multi-query: richest contextual query first (works for wiki + papers)."""
    name = intent.person_name
    queries: list[str] = []

    if intent.display_query:
        queries.append(intent.display_query)
    if intent.institution and intent.role:
        queries.append(f"{intent.institution} {name} {intent.role}")
    if intent.institution:
        queries.append(f"{name} {intent.institution}")
        queries.append(f'author:"{name}" {intent.institution}')
    else:
        queries.append(name)
        if intent.role:
            queries.append(f"{name} {intent.role}")
        queries.append(f'author:"{name}"')
    if intent.topic:
        queries.append(f"{name} {intent.topic}")
    if re.search(r"[A-Za-z]", name):
        queries.append(f"{name} publications")

    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        q = " ".join(q.split())
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out[:8]


# Generic entity-type signals (language-agnostic heuristics, not name blacklists)
_PERSON_PAGE_SIGNALS = (
    "教授",
    "副教授",
    "学者",
    "出生",
    "生于",
    "毕业于",
    "研究方向",
    "博士",
    "院士",
    "biography",
    "academic",
    "professor",
    "faculty",
    "born",
    "phd",
    "researcher",
    "alumni",
)
_PLACE_PAGE_SIGNALS = (
    "省会",
    "行政区",
    "地级市",
    "直辖市",
    "人口",
    "平方公里",
    "地理位置",
    "municipality",
    "prefecture",
    "coordinates",
    "elevation",
    "气候",
    "行政区划",
    "city in",
    "province of",
)


def person_entity_score(title: str, abstract: str, *, person_name: str, institution: str | None) -> float:
    """Higher = more like a person/entity page; lower = geographic or unrelated."""
    blob = f"{title} {abstract}"
    blob_l = blob.lower()
    score = 0.0
    for s in _PERSON_PAGE_SIGNALS:
        if s.lower() in blob_l:
            score += 1.0
    for s in _PLACE_PAGE_SIGNALS:
        if s.lower() in blob_l:
            score -= 1.5
    if person_name and person_name in title:
        score += 0.5
    if institution and institution in blob:
        score += 2.0
    # Bare title equals short name with heavy place signals → strongly non-person
    if title.strip() == person_name and score < 0:
        score -= 2.0
    return score
