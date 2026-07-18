"""Rank person-works by author / affiliation / person-entity signals (no name blacklists)."""

from __future__ import annotations

import re
from typing import Any

from app.services.assistant.person_search_intent import PersonSearchIntent, person_entity_score


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip().lower())


def _author_match_score(authors: list[Any], person_name: str) -> float:
    target = _norm(person_name)
    if not target:
        return 0.0
    best = 0.0
    for a in authors or []:
        name = _norm(str(a))
        if not name:
            continue
        if name == target:
            best = max(best, 1.0)
        elif target in name or name in target:
            best = max(best, 0.75)
        elif len(target) >= 2 and target[-2:] in name:
            best = max(best, 0.45)
    return best


def _institution_match_score(blob: str, institution: str | None) -> float:
    if not institution:
        return 0.0
    b = blob.lower()
    inst = institution.lower()
    if inst in b:
        return 1.0
    tokens = [t for t in re.split(r"[\s·,，/|]+", institution) if len(t) >= 2]
    hits = sum(1 for t in tokens if t.lower() in b)
    if hits and tokens:
        return min(1.0, 0.35 * hits)
    return 0.0


def score_work_for_person(work: dict[str, Any], intent: PersonSearchIntent) -> float:
    title = str(work.get("title") or "")
    abstract = str(work.get("abstract_preview") or "")
    authors = list(work.get("authors") or [])
    journal = str(work.get("journal") or "")
    blob = f"{title} {abstract} {journal} {' '.join(str(a) for a in authors)}"

    entity = person_entity_score(
        title, abstract, person_name=intent.person_name, institution=intent.institution
    )
    # Drop clear place/geo encyclopedia hits when we have better person evidence available
    # (caller may still keep low-score items; we mark heavily negative)
    if entity <= -2.5 and float(_author_match_score(authors, intent.person_name)) < 0.45:
        work["author_match_score"] = 0.0
        work["institution_match_score"] = 0.0
        work["person_entity_score"] = round(entity, 3)
        work["person_rank_score"] = -10.0
        return -10.0

    author_s = _author_match_score(authors, intent.person_name)
    inst_s = _institution_match_score(blob, intent.institution)
    topic_s = 0.0
    if intent.topic and intent.topic.lower() in blob.lower():
        topic_s = 0.4

    source = str(work.get("source") or "").lower()
    credibility = 0.2
    if source in {"semantic_scholar", "crossref", "openalex", "arxiv"}:
        credibility = 0.5
    elif source in {"wikipedia", "wiki"}:
        credibility = 0.35 if entity > 0 else 0.05
    elif source == "web":
        credibility = 0.25

    meta = 0.1 if work.get("year") else 0.0
    meta += 0.1 if work.get("url") else 0.0
    meta += 0.1 if abstract else 0.0

    score = (
        author_s * 4.0
        + inst_s * 2.5
        + max(entity, -2.0) * 0.8
        + credibility
        + topic_s
        + meta
    )
    if intent.require_author_match and author_s < 0.45 and source in {"wikipedia", "wiki", "web"}:
        # Still allow if entity score strongly person-like + institution matched
        if not (entity >= 1.5 and inst_s >= 0.5):
            score -= 1.5

    work["author_match_score"] = round(author_s, 3)
    work["institution_match_score"] = round(inst_s, 3)
    work["person_entity_score"] = round(entity, 3)
    work["person_rank_score"] = round(score, 3)
    return score


def rank_works_for_person(works: list[dict[str, Any]], intent: PersonSearchIntent) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for w in works:
        item = dict(w)
        s = score_work_for_person(item, intent)
        if s <= -5:
            continue
        out.append(item)
    out.sort(key=lambda x: float(x.get("person_rank_score") or 0), reverse=True)
    return out


def build_author_candidates(works: list[dict[str, Any]], intent: PersonSearchIntent) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for w in works:
        authors = [str(a).strip() for a in (w.get("authors") or []) if str(a).strip()]
        matched = [a for a in authors if intent.person_name in a or a in intent.person_name]
        if not matched and float(w.get("author_match_score") or 0) >= 0.45:
            matched = authors[:1]
        if not matched and float(w.get("person_entity_score") or 0) >= 1.5:
            matched = [intent.person_name]
        if not matched:
            continue
        display = matched[0]
        inst_hint = intent.institution or ""
        journal = str(w.get("journal") or "")
        blob = f"{w.get('title')} {journal} {w.get('abstract_preview')}"
        if intent.institution and intent.institution in blob:
            inst_hint = intent.institution
        key = f"{display}|{inst_hint}"
        bucket = buckets.get(key)
        if not bucket:
            bucket = {
                "id": key,
                "display_name": display,
                "institution": inst_hint or None,
                "match_score": float(w.get("person_rank_score") or 0),
                "work_count": 0,
                "sample_titles": [],
                "evidence": [],
            }
            buckets[key] = bucket
        bucket["work_count"] += 1
        bucket["match_score"] = max(bucket["match_score"], float(w.get("person_rank_score") or 0))
        title = str(w.get("title") or "").strip()
        if title and title not in bucket["sample_titles"]:
            bucket["sample_titles"].append(title[:120])
        if w.get("url") and len(bucket["evidence"]) < 3:
            bucket["evidence"].append({"title": title[:120], "url": w.get("url"), "source": w.get("source")})
    return sorted(buckets.values(), key=lambda c: (c["match_score"], c["work_count"]), reverse=True)[:8]
