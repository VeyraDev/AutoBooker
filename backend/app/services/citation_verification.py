"""Citation metadata verification helpers.

The service intentionally separates cheap local classification from optional
external lookups. Review snapshots can always use the local result, while a
manual refresh/background job can call ``verify_citation_metadata`` with DOI and
search providers.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Callable

from app.models.citation import CitationSource

VERIFICATION_STATUSES = {
    "verified",
    "probable",
    "user_uploaded_only",
    "needs_verification",
    "mismatch",
    "unreachable",
}

ACADEMIC_TYPES = {"journal_article", "conference_paper", "dissertation", "j", "c", "d", "article", "paper"}


LookupDoi = Callable[[str], dict[str, Any] | None]
SearchWorks = Callable[[str, int], list[dict[str, Any]]]
VerifyCitation = Callable[..., dict[str, Any]]


def citation_to_verification_dict(citation: Any) -> dict[str, Any]:
    """Return a cheap verification snapshot from stored citation metadata."""
    paper = _citation_to_paper(citation)
    missing = missing_metadata_fields(paper)
    source = _source_value(getattr(citation, "source", None))
    external_source = str(getattr(citation, "external_source", None) or paper.get("source") or "").strip().lower()
    has_abstract = bool(str(getattr(citation, "abstract_preview", None) or paper.get("abstract_preview") or "").strip())
    has_external_id = bool((getattr(citation, "doi", None) or paper.get("doi")) or getattr(citation, "external_id", None))

    status = "needs_verification"
    reasons: list[str] = []
    if source == CitationSource.uploaded_file.value:
        if _is_academic(paper) and not has_abstract:
            status = "needs_verification"
            reasons.append("uploaded_academic_missing_abstract")
        elif missing:
            status = "needs_verification"
            reasons.append("uploaded_metadata_incomplete")
        else:
            status = "user_uploaded_only"
            reasons.append("user_uploaded_metadata_complete")
    elif external_source in {"crossref", "openalex", "semantic_scholar", "semanticscholar"} or has_external_id:
        status = "verified" if (paper.get("doi") or has_external_id) and not missing else "probable"
        reasons.append("from_public_literature_source")
    elif not missing:
        status = "probable"
        reasons.append("metadata_complete_without_external_match")
    else:
        status = "needs_verification"
        reasons.append("metadata_incomplete")

    return {
        "verification_status": status,
        "source_match": {
            "source": source or external_source or "unknown",
            "external_source": external_source or None,
            "has_doi": bool(paper.get("doi")),
            "has_external_id": has_external_id,
            "has_abstract": has_abstract,
        },
        "missing_fields": missing,
        "recommended_search_query": recommended_search_query(paper),
        "reasons": reasons,
    }


def verify_citation_metadata(
    citation_or_paper: Any,
    *,
    lookup_doi: LookupDoi | None = None,
    search_openalex: SearchWorks | None = None,
    search_semantic_scholar: SearchWorks | None = None,
    rows: int = 5,
) -> dict[str, Any]:
    """Verify a citation using DOI first, then title search providers.

    Provider callables are injectable so tests and background jobs can control
    network behavior. The function never fabricates metadata; it only reports
    match strength and recommended next steps.
    """
    paper = _citation_to_paper(citation_or_paper)
    local = citation_to_verification_dict(citation_or_paper)
    missing = missing_metadata_fields(paper)
    doi = _normalize_doi(paper.get("doi"))
    providers_checked: list[str] = []
    errors: list[str] = []
    candidates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    if doi and lookup_doi:
        providers_checked.append("crossref_doi")
        try:
            match = lookup_doi(doi)
            if match:
                match = dict(match)
                match.setdefault("source", "crossref")
                compared = compare_citation_metadata(paper, match)
                compared["doi_match"] = _normalize_doi(match.get("doi")) == doi
                candidates.append(("crossref_doi", match, compared))
        except Exception as exc:  # pragma: no cover - defensive logging-free guard
            errors.append(f"crossref_doi:{exc.__class__.__name__}")

    query = recommended_search_query(paper)
    if query and search_openalex:
        providers_checked.append("openalex")
        try:
            for match in _call_search_provider(search_openalex, query, rows) or []:
                compared = compare_citation_metadata(paper, match)
                candidates.append(("openalex", match, compared))
        except Exception as exc:  # pragma: no cover
            errors.append(f"openalex:{exc.__class__.__name__}")
    if query and search_semantic_scholar:
        providers_checked.append("semantic_scholar")
        try:
            for match in _call_search_provider(search_semantic_scholar, query, rows) or []:
                compared = compare_citation_metadata(paper, match)
                candidates.append(("semantic_scholar", match, compared))
        except Exception as exc:  # pragma: no cover
            errors.append(f"semantic_scholar:{exc.__class__.__name__}")

    if not providers_checked:
        return local
    if not candidates:
        status = "unreachable" if errors and len(errors) == len(providers_checked) else local["verification_status"]
        if status == "probable":
            status = "needs_verification"
        return {
            **local,
            "verification_status": status,
            "providers_checked": providers_checked,
            "lookup_errors": errors,
            "source_match": {**local.get("source_match", {}), "best_score": 0.0},
        }

    provider, best, score = max(candidates, key=lambda row: _overall_score(row[2]))
    overall = _overall_score(score)
    doi_mismatch = bool(doi and best.get("doi") and _normalize_doi(best.get("doi")) != doi)
    title_mismatch = score["title_similarity"] < 0.45
    if doi_mismatch or (doi and title_mismatch):
        status = "mismatch"
    elif score.get("doi_match") or overall >= 0.86:
        status = "verified"
    elif overall >= 0.68:
        status = "probable"
    else:
        status = "needs_verification"

    return {
        "verification_status": status,
        "source_match": {
            "provider": provider,
            "best_score": round(overall, 3),
            "title_similarity": round(score["title_similarity"], 3),
            "author_overlap": round(score["author_overlap"], 3),
            "year_match": score["year_match"],
            "doi_match": bool(score.get("doi_match")),
            "matched_title": str(best.get("title") or "")[:300],
            "matched_authors": list(best.get("authors") or [])[:6],
            "matched_year": best.get("year"),
            "matched_doi": _normalize_doi(best.get("doi")),
            "matched_url": best.get("url") or "",
        },
        "missing_fields": missing,
        "recommended_search_query": query,
        "providers_checked": providers_checked,
        "lookup_errors": errors,
        "reasons": _verification_reasons(status, score, missing),
    }


def verify_citation_with_public_sources(citation_or_paper: Any, *, rows: int = 5) -> dict[str, Any]:
    """Verify against the public providers already used by literature search."""
    from app.agents.literature_agent import lookup_crossref_by_doi, search_semantic_scholar
    from app.services.literature_openalex import search_openalex

    return verify_citation_metadata(
        citation_or_paper,
        lookup_doi=lookup_crossref_by_doi,
        search_openalex=search_openalex,
        search_semantic_scholar=search_semantic_scholar,
        rows=rows,
    )


def refresh_citation_verification(
    citation: Any,
    *,
    verifier: VerifyCitation | None = None,
    rows: int = 5,
) -> dict[str, Any]:
    """Run external verification and persist the latest result on a citation row."""
    fn = verifier or verify_citation_with_public_sources
    try:
        result = fn(citation, rows=rows)
    except TypeError:
        try:
            result = fn(citation)
        except Exception as exc:  # pragma: no cover - defensive external boundary
            result = _unreachable_verification_result(citation, exc)
    except Exception as exc:  # pragma: no cover - defensive external boundary
        result = _unreachable_verification_result(citation, exc)
    result = _normalized_verification_result(citation, result)
    setattr(citation, "verification_status", result["verification_status"])
    setattr(citation, "verification_result", result)
    setattr(citation, "last_verified_at", datetime.now(timezone.utc))
    return result


def persisted_citation_verification_dict(citation: Any) -> dict[str, Any]:
    """Return stored verification when present, otherwise cheap local status."""
    stored = getattr(citation, "verification_result", None)
    status = str(getattr(citation, "verification_status", None) or "").strip()
    if isinstance(stored, dict):
        stored_status = str(stored.get("verification_status") or status).strip()
        if stored_status in VERIFICATION_STATUSES:
            result = dict(stored)
            result["verification_status"] = stored_status
            result.setdefault("source_match", {})
            result.setdefault("missing_fields", [])
            result.setdefault("recommended_search_query", recommended_search_query(_citation_to_paper(citation)))
            result["persisted"] = True
            last_verified = getattr(citation, "last_verified_at", None)
            if last_verified:
                result["last_verified_at"] = last_verified.isoformat()
            return result
    return citation_to_verification_dict(citation)


def compare_citation_metadata(source: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "title_similarity": _title_similarity(source.get("title"), candidate.get("title")),
        "author_overlap": _author_overlap(source.get("authors") or [], candidate.get("authors") or []),
        "year_match": _year_match(source.get("year"), candidate.get("year")),
    }


def missing_metadata_fields(paper: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not str(paper.get("title") or "").strip():
        missing.append("title")
    if not [a for a in (paper.get("authors") or []) if str(a).strip()]:
        missing.append("authors")
    if not paper.get("year") and not paper.get("doi") and not paper.get("url"):
        missing.append("year_or_doi_or_url")
    if _is_academic(paper) and not str(paper.get("abstract_preview") or "").strip():
        missing.append("abstract")
    return missing


def recommended_search_query(paper: dict[str, Any]) -> str:
    title = str(paper.get("title") or "").strip()
    authors = [str(a).strip() for a in (paper.get("authors") or []) if str(a).strip()]
    year = str(paper.get("year") or "").strip()
    parts = [title]
    if authors:
        parts.append(authors[0])
    if year:
        parts.append(year)
    return " ".join(part for part in parts if part).strip()


def _citation_to_paper(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return dict(obj)
    return {
        "title": getattr(obj, "title", "") or "",
        "authors": list(getattr(obj, "authors", None) or []),
        "year": getattr(obj, "year", None),
        "journal": getattr(obj, "journal", "") or "",
        "doi": getattr(obj, "doi", "") or "",
        "url": getattr(obj, "url", "") or "",
        "source": _source_value(getattr(obj, "source", None)),
        "external_source": getattr(obj, "external_source", None) or "",
        "external_id": getattr(obj, "external_id", None) or "",
        "document_type": getattr(obj, "document_type", None) or "",
        "publisher": getattr(obj, "publisher", None) or "",
        "volume": getattr(obj, "volume", None) or "",
        "issue": getattr(obj, "issue", None) or "",
        "pages": getattr(obj, "pages", None) or "",
        "abstract_preview": getattr(obj, "abstract_preview", None) or "",
    }


def _call_search_provider(func: SearchWorks, query: str, rows: int) -> list[dict[str, Any]]:
    try:
        return func(query, rows) or []
    except TypeError:
        try:
            return func(query, limit=rows) or []  # type: ignore[call-arg]
        except TypeError:
            return func(query, rows=rows) or []  # type: ignore[call-arg]


def _source_value(raw: Any) -> str:
    return str(getattr(raw, "value", raw) or "").strip()


def _normalize_doi(raw: Any) -> str:
    doi = str(raw or "").strip().lower()
    doi = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    doi = doi.removeprefix("doi:")
    return doi.rstrip(".,;")


def _normalize_text(text: Any) -> str:
    s = str(text or "").lower()
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[\s，。！？；：、“”‘’（）()\[\]【】,.!?;:\"'\-—–_/]+", "", s)
    return s


def _title_similarity(a: Any, b: Any) -> float:
    left = _normalize_text(a)
    right = _normalize_text(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _author_overlap(source_authors: list[Any], candidate_authors: list[Any]) -> float:
    left = {_normalize_author(a) for a in source_authors if _normalize_author(a)}
    right = {_normalize_author(a) for a in candidate_authors if _normalize_author(a)}
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def _normalize_author(raw: Any) -> str:
    text = _normalize_text(raw)
    # For western names, matching surname is often enough across Crossref/Semantic
    # formatting differences; for CJK names the normalized full name remains short.
    words = re.findall(r"[a-z]+", str(raw or "").lower())
    if words:
        return words[-1]
    return text


def _year_match(a: Any, b: Any) -> bool | None:
    try:
        ay = int(a)
        by = int(b)
    except (TypeError, ValueError):
        return None
    return abs(ay - by) <= 1


def _overall_score(score: dict[str, Any]) -> float:
    title = float(score.get("title_similarity") or 0)
    author = float(score.get("author_overlap") or 0)
    year = 0.12 if score.get("year_match") is True else 0.0
    doi = 0.2 if score.get("doi_match") else 0.0
    return min(1.0, title * 0.62 + author * 0.18 + year + doi)


def _is_academic(paper: dict[str, Any]) -> bool:
    doc_type = str(paper.get("document_type") or paper.get("type") or "").strip().lower()
    return doc_type in ACADEMIC_TYPES


def _verification_reasons(status: str, score: dict[str, Any], missing: list[str]) -> list[str]:
    reasons = [status]
    if missing:
        reasons.append("missing:" + ",".join(missing))
    if score.get("doi_match"):
        reasons.append("doi_matched")
    if float(score.get("title_similarity") or 0) >= 0.86:
        reasons.append("title_matched")
    if float(score.get("author_overlap") or 0) > 0:
        reasons.append("author_matched")
    if score.get("year_match") is True:
        reasons.append("year_matched")
    return reasons


def _normalized_verification_result(citation: Any, raw: Any) -> dict[str, Any]:
    local = citation_to_verification_dict(citation)
    result = dict(raw) if isinstance(raw, dict) else {}
    status = str(result.get("verification_status") or "").strip()
    if status not in VERIFICATION_STATUSES:
        status = local["verification_status"]
    result["verification_status"] = status
    result.setdefault("source_match", local.get("source_match") or {})
    result.setdefault("missing_fields", local.get("missing_fields") or [])
    result.setdefault("recommended_search_query", local.get("recommended_search_query") or "")
    result.setdefault("reasons", local.get("reasons") or [status])
    return result


def _unreachable_verification_result(citation: Any, exc: Exception) -> dict[str, Any]:
    local = citation_to_verification_dict(citation)
    return {
        **local,
        "verification_status": "unreachable",
        "lookup_errors": [f"refresh:{exc.__class__.__name__}"],
        "reasons": [*(local.get("reasons") or []), "external_refresh_failed"],
    }
