"""Project startup assistant — multi-turn conversation (single book_settings)."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.constants.style_types import StyleType
from app.llm.client import LLMClient
from app.llm.providers import resolve_assistant_model
from app.models.assistant_turn import AssistantTrace, AssistantTurn
from app.models.book import Book, BookType, CitationStyle
from app.models.material import ConfirmationStatus, WritingRequirement
from app.models.user import User
from app.prompts.assistant.global_system import global_turn_output_instruction
from app.prompts.assistant.startup_system import (
    QUICK_FILL_INSTRUCTION,
    STARTUP_ASSISTANT_SYSTEM,
    startup_turn_output_instruction,
)
from app.services.assistant.book_settings_context import (
    BOOK_SETTING_KEYS,
    build_startup_context,
    current_book_settings,
    get_setting_origins,
    protected_origins,
    set_setting_origin,
)
from app.services.assistant.context_compression_service import ContextCompressionService
from app.services.assistant.external_search_service import ExternalSearchService
from app.services.assistant.project_memory_service import ProjectMemoryService
from app.services.assistant.quick_fill_ops import record_quick_fill, snapshot_settings, undo_quick_fill
from app.services.assistant.tool_orchestrator import ToolOrchestrator
from app.services.literature_search_service import LiteratureSearchService
from app.services.sources.source_library_service import SourceLibraryService
from app.services.writing.writing_basis_service import WritingBasisService
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_VALID_STYLES = {s.value for s in StyleType}
_MAX_TOOL_ITERS = 4
_TOOL_RESULT_CHARS = 10000


def _trim_papers(items: Any, limit: int = 30) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for p in items[:limit]:
        if not isinstance(p, dict):
            continue
        out.append(
            {
                "title": p.get("title"),
                "authors": list(p.get("authors") or [])[:5],
                "year": p.get("year"),
                "source": p.get("source"),
                "source_label": p.get("source_label"),
                "url": p.get("url"),
                "doi": p.get("doi"),
                "external_id": p.get("external_id"),
                "abstract_preview": (str(p.get("abstract_preview") or "")[:200] or None),
            }
        )
    return out


def _compact_search_result(sr: dict[str, Any]) -> dict[str, Any]:
    result = sr.get("result") if isinstance(sr.get("result"), dict) else {}
    compact_result: dict[str, Any] = {
        "papers": _trim_papers(result.get("papers")),
        "github": _trim_papers(result.get("github")),
        "wiki": _trim_papers(result.get("wiki")),
        "official_docs": _trim_papers(result.get("official_docs")),
        "items": _trim_papers(result.get("items")),
        "refined_queries": list(result.get("refined_queries") or [])[:8],
        "warnings": list(result.get("warnings") or [])[:5],
        "source_hint": result.get("source_hint"),
        "query": result.get("query") or sr.get("raw_query"),
    }
    # person_works fields
    for key in ("person", "institution", "role", "candidates", "works", "research_directions", "source_scope", "needs_disambiguation"):
        if key in result:
            compact_result[key] = result.get(key)
    return {
        "ok": sr.get("ok", True),
        "mode": sr.get("mode"),
        "search_type": sr.get("search_type"),
        "raw_query": sr.get("raw_query"),
        "queries": list(sr.get("queries") or [])[:8],
        "summary": sr.get("summary") or "",
        "auto_ingested": False,
        "result": compact_result,
    }


def extract_search_result_from_turn(turn: AssistantTurn) -> dict[str, Any] | None:
    """Recover search payload from persisted turn (basis_patch or tool_calls)."""
    meta = turn.basis_patch if isinstance(turn.basis_patch, dict) else {}
    stored = meta.get("search_result")
    if isinstance(stored, dict) and (stored.get("result") or stored.get("summary")):
        return stored
    tools = turn.tool_calls if isinstance(turn.tool_calls, list) else []
    for r in tools:
        if not isinstance(r, dict) or not r.get("ok"):
            continue
        if r.get("name") not in {"search_references", "search_literature", "search_person_works"}:
            continue
        payload = r.get("data") if isinstance(r.get("data"), dict) else {}
        wrapped = {
            "ok": True,
            "mode": payload.get("mode") or "user_query",
            "search_type": payload.get("search_type")
            or ("person_works" if r.get("name") == "search_person_works" else "literature"),
            "raw_query": payload.get("raw_query") or "",
            "queries": payload.get("queries") or payload.get("queries_used") or [],
            "summary": payload.get("summary") or "",
            "result": payload.get("result") if "result" in payload else payload,
            "auto_ingested": False,
        }
        return _compact_search_result(wrapped)
    return None


_STARTUP_TOOL_NAMES = frozenset(
    {
        "retrieve_source_context",
        "inspect_workbook",
        "read_sheet_range",
        "search_references",
        "suggest_book_settings",
        "assess_outline_sources",
        # legacy still accepted inside loop
        "prepare_search",
        "search_literature",
        "search_person_works",
        "list_sources",
    }
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _is_placeholder_title(title: str | None) -> bool:
    t = (title or "").strip()
    if not t:
        return True
    if t in {"未命名", "未命名书稿", "新书稿"}:
        return True
    if t.startswith("书稿") and t[2:].isdigit():
        return True
    return False


def _decision_origin(decision_type: str) -> str:
    mapping = {
        "explicit": "user_explicit",
        "inferred": "assistant_inferred",
        "suggested": "assistant_inferred",
        "default": "system_default",
    }
    return mapping.get((decision_type or "").strip(), "assistant_inferred")


def _filter_patch_by_origins(
    book: Book,
    patch: dict[str, Any],
    setting_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Drop inferred/suggested/default updates that would overwrite user_manual/user_explicit."""
    origins = get_setting_origins(book)
    decisions_by_field = {
        str(d.get("field")): d for d in setting_decisions if isinstance(d, dict) and d.get("field")
    }
    protected = protected_origins()
    out: dict[str, Any] = {}
    for key, value in patch.items():
        if value is None:
            continue
        if key not in BOOK_SETTING_KEYS:
            continue
        meta = origins.get(key) if isinstance(origins.get(key), dict) else {}
        cur_origin = str(meta.get("origin") or "")
        decision = decisions_by_field.get(key) or {}
        dtype = str(decision.get("decision_type") or "inferred")
        if cur_origin in protected and dtype not in {"explicit"}:
            continue
        out[key] = value
    return out


def _apply_book_settings_patch(
    book: Book,
    patch: dict[str, Any],
    *,
    setting_decisions: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Apply patch; return list of fields actually updated."""
    if not patch:
        return []
    decisions = setting_decisions or []
    decisions_by_field = {
        str(d.get("field")): d for d in decisions if isinstance(d, dict) and d.get("field")
    }
    updated: list[str] = []

    def _mark(field: str) -> None:
        d = decisions_by_field.get(field) or {}
        set_setting_origin(book, field, _decision_origin(str(d.get("decision_type") or "inferred")))
        updated.append(field)

    title = patch.get("title")
    if isinstance(title, str) and title.strip():
        cleaned = title.strip()[:500]
        if book.allow_title_optimization or _is_placeholder_title(book.title):
            if cleaned and not _is_placeholder_title(cleaned):
                book.title = cleaned
                _mark("title")

    classified = False
    bt = patch.get("book_type")
    if isinstance(bt, str) and bt.strip().lower() in ("nonfiction", "academic"):
        book.book_type = BookType(bt.strip().lower())
        classified = True
        _mark("book_type")

    st = patch.get("style_type")
    if isinstance(st, str) and st.strip() in _VALID_STYLES:
        book.style_type = st.strip()
        classified = True
        _mark("style_type")

    if classified:
        from app.services.writing.project_seed import _pair_type_and_style, mark_classification_source

        paired_type, paired_style = _pair_type_and_style(
            book.book_type.value if book.book_type else "",
            book.style_type or "",
            fallback_type=book.book_type or BookType.nonfiction,
            fallback_style=book.style_type or "",
        )
        book.book_type = paired_type
        book.style_type = paired_style
        mark_classification_source(book, "assistant")

    if patch.get("target_audience"):
        book.target_audience = str(patch["target_audience"]).strip()[:500]
        _mark("target_audience")

    discs = patch.get("disciplines")
    if isinstance(discs, list):
        cleaned = [str(d).strip()[:100] for d in discs if str(d).strip()][:12]
        if cleaned:
            book.disciplines = cleaned
            book.discipline = cleaned[0]
            _mark("disciplines")

    tags = patch.get("topic_tags")
    if isinstance(tags, list):
        cleaned_tags = [str(t).strip()[:80] for t in tags if str(t).strip()][:40]
        if cleaned_tags:
            book.topic_tags = cleaned_tags
            _mark("topic_tags")

    if patch.get("topic_brief"):
        book.topic_brief = str(patch["topic_brief"]).strip()[:20_000]
        _mark("topic_brief")

    if "target_words" in patch and patch.get("target_words") is not None:
        try:
            words = int(patch.get("target_words") or 0)
            if 10_000 <= words <= 500_000:
                book.target_words = words
                _mark("target_words")
        except (TypeError, ValueError):
            pass

    cs = patch.get("citation_style")
    if isinstance(cs, str):
        key = cs.strip().lower()
        if key in ("none", "无", "无需"):
            book.citation_style = None
            _mark("citation_style")
        elif key in {c.value for c in CitationStyle}:
            book.citation_style = CitationStyle(key)
            _mark("citation_style")

    return updated


def _silent_sync_basis(book: Book, basis: Any) -> None:
    """Downstream compatibility only — not a second settings form."""
    if book.topic_brief:
        basis.direction = str(book.topic_brief)[:20_000]
    if book.target_audience:
        basis.target_readers = str(book.target_audience)[:500]


def _persist_outline_route(book: Book, route: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(route, dict):
        return None
    mode = str(route.get("mode") or "from_settings").strip()
    if mode not in {"from_settings", "complete_existing_outline", "use_existing_outline"}:
        mode = "from_settings"
    normalized = {
        "mode": mode,
        "source_id": str(route.get("source_id") or "").strip() or None,
        "reason": str(route.get("reason") or "").strip()[:1000],
        "confidence": float(route["confidence"]) if route.get("confidence") is not None else None,
        "needs_confirmation": bool(route.get("needs_confirmation")),
        "candidate_source_ids": [
            str(x) for x in (route.get("candidate_source_ids") or []) if str(x).strip()
        ][:10],
    }
    settings = dict(book.ai_inferred_settings) if isinstance(book.ai_inferred_settings, dict) else {}
    settings["outline_route"] = normalized
    book.ai_inferred_settings = settings
    return normalized


def _apply_extracted_requirements(db: Session, book: Book, items: list[Any]) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    for item in items[:30]:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if len(content) < 2:
            continue
        category = str(item.get("category") or "other").strip()[:64] or "other"
        strength = str(item.get("strength") or "should").strip()
        if strength not in {"must", "should", "preference"}:
            strength = "should"
        exists = (
            db.query(WritingRequirement.id)
            .filter(
                WritingRequirement.book_id == book.id,
                WritingRequirement.content == content[:2000],
                WritingRequirement.active.is_(True),
            )
            .first()
        )
        if exists:
            continue
        row = WritingRequirement(
            book_id=book.id,
            source_file_id=None,
            content=content[:2000],
            category=f"extracted_{category}",
            strength=strength if strength != "preference" else "should",
            scope="book",
            active=True,
            confirmation_status=ConfirmationStatus.effective
            if item.get("confirmed", True)
            else ConfirmationStatus.pending,
        )
        db.add(row)
        saved.append(
            {
                "category": category,
                "content": content[:500],
                "strength": strength,
                "source_id": item.get("source_id"),
            }
        )
    return saved


_FIELD_LABELS_ZH = {
    "title": "书名",
    "book_type": "一级分类",
    "style_type": "二级体裁",
    "target_audience": "目标读者",
    "disciplines": "学科领域",
    "topic_brief": "主题要点",
    "target_words": "目标字数",
    "topic_tags": "话题标签",
    "citation_style": "引用格式",
}

_MACHINE_LEAK_RE = (
    "topic_brief",
    "disciplines",
    "topic_tags",
    "target_audience",
    "book_type",
    "style_type",
    "target_words",
    "citation_style",
    "book_settings_patch",
    "setting_decisions",
    "decision_type",
    "[object Object]",
)


def _format_patch_value(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(x).strip() for x in value if str(x).strip())
    return str(value).strip()


def _ensure_user_facing_update_message(
    message: str,
    patch: dict[str, Any],
    decisions: list[dict[str, Any]],
) -> str:
    """Strip machine field dumps; if patch applied but reply hides it, append a natural summary."""
    text = (message or "").strip()
    # Drop lines that are clearly machine-field dumps
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue
        if stripped.startswith("[object Object]"):
            continue
        if any(tok in stripped for tok in ("book_settings_patch", "setting_decisions", "decision_type")):
            continue
        # Lines like "topic_brief: ..." or "disciplines: ['x']"
        if any(stripped.startswith(f"{k}:") or stripped.startswith(f"{k}：") for k in _FIELD_LABELS_ZH):
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines).strip()

    if not patch:
        return text

    # If reply already explains updates in Chinese labels, keep it
    zh_hits = sum(1 for label in _FIELD_LABELS_ZH.values() if label in text)
    if zh_hits >= min(2, len(patch)) and not any(tok in text for tok in _MACHINE_LEAK_RE):
        return text

    reasons = {
        str(d.get("field")): str(d.get("reason") or "").strip()
        for d in decisions
        if isinstance(d, dict) and d.get("field")
    }
    bullets: list[str] = []
    for key, value in patch.items():
        label = _FIELD_LABELS_ZH.get(key, key)
        rendered = _format_patch_value(value)
        if not rendered:
            continue
        reason = reasons.get(key) or ""
        if reason and len(reason) < 120:
            bullets.append(f"- {label}：{rendered}（{reason}）")
        else:
            bullets.append(f"- {label}：{rendered}")
    if not bullets:
        return text

    summary = "本轮已写入正式设定：\n" + "\n".join(bullets)
    if not text:
        return summary
    # If text still leaks machine keys, prefer summary + cleaned remainder without dumps
    if any(tok in text for tok in _MACHINE_LEAK_RE) or zh_hits < 1:
        return f"{summary}\n\n{text}" if text and not any(tok in text for tok in _MACHINE_LEAK_RE[:8]) else summary
    return f"{text}\n\n{summary}"


def _book_support_query(book: Book) -> str:
    parts = [
        (book.topic_brief or "").strip(),
        " ".join(str(d) for d in (book.disciplines or [])[:3]),
        " ".join(str(t) for t in (book.topic_tags or [])[:6]),
        (book.target_audience or "").strip()[:120],
        (book.style_type or "").strip(),
    ]
    return " ".join(p for p in parts if p).strip()[:800]


class ProjectAssistantService:
    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMClient()
        self._basis = WritingBasisService(db)
        self._sources = SourceLibraryService(db)
        self._tools = ToolOrchestrator(db)
        self._memories = ProjectMemoryService(db)
        self._compression = ContextCompressionService(db)
        self._external = ExternalSearchService()
        self._literature = LiteratureSearchService(db)

    def _build_user_prompt(
        self,
        book: Book,
        message: str,
        *,
        assistant_mode: str,
        chapter_index: int | None = None,
    ) -> str:
        history = self._compression.recent_turns(book.id, limit=8)
        recent = []
        for turn in history:
            recent.append({"role": "user", "text": (turn.user_message or "")[:800]})
            recent.append({"role": "assistant", "text": (turn.assistant_message or "")[:800]})
        ctx = build_startup_context(
            self.db,
            book,
            assistant_mode=assistant_mode,
            user_message=message,
            recent_conversation=recent,
        )
        if chapter_index is not None:
            return f"""当前章节：第 {chapter_index} 章
上下文：
{json.dumps(ctx, ensure_ascii=False)[:8000]}

用户本轮输入：
{message}

{global_turn_output_instruction()}"""
        parts = [
            "当前书稿设定上下文（轻量目录；详细内容请用工具读取）：",
            json.dumps(ctx, ensure_ascii=False)[:6000],
        ]
        if assistant_mode == "quick_fill":
            parts.extend(["", QUICK_FILL_INSTRUCTION])
        parts.extend(["", startup_turn_output_instruction()])
        return "\n".join(parts)

    def _parse_turn_response(self, raw: str) -> dict[str, Any]:
        text = (raw or "").strip()
        if not text:
            raise RuntimeError("模型未返回有效内容，请稍后重试")
        try:
            return parse_llm_json(text)
        except (json.JSONDecodeError, ValueError) as exc:
            if text.startswith("{"):
                raise RuntimeError("助手返回格式异常，请重试") from exc
            return {
                "assistant_message": text[:8000],
                "book_settings_patch": {},
                "setting_decisions": [],
                "extracted_requirements": [],
                "tool_calls": [],
                "outline_route": None,
                "clarification": {"required": False},
            }

    @staticmethod
    def _normalize_tool_calls(data: dict[str, Any]) -> list[dict[str, Any]]:
        calls = [c for c in _as_list(data.get("tool_calls")) if isinstance(c, dict) and c.get("name")]
        # Legacy: search_request → search_references tool
        search_req = _as_dict(data.get("search_request"))
        if search_req.get("required") and not any(
            str(c.get("name")) in {"search_references", "search_literature", "search_person_works"} for c in calls
        ):
            calls.append(
                {
                    "name": "search_references",
                    "arguments": {
                        "mode": search_req.get("mode") or "user_query",
                        "raw_query": search_req.get("raw_query") or "",
                        "search_type": search_req.get("search_type") or "auto",
                    },
                }
            )
        return calls

    def _run_startup_tool_loop(
        self,
        book: Book,
        user: User,
        *,
        message: str,
        mode: str,
        model: str,
        chapter_index: int | None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
        """Assistant ↔ tools ↔ assistant until final JSON (no tool_calls)."""
        system = self._system_prompt(chapter_index)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": self._build_user_prompt(
                    book, message, assistant_mode=mode, chapter_index=chapter_index
                ),
            },
        ]
        executed_tools: list[dict[str, Any]] = []
        search_result: dict[str, Any] | None = None
        data: dict[str, Any] = {}

        for iteration in range(_MAX_TOOL_ITERS):
            raw = self.llm.chat_completion(
                messages,
                model=model,
                max_tokens=4000,
                temperature=0.4,
                disable_thinking=True,
            )
            data = self._parse_turn_response(raw)
            tool_calls = self._normalize_tool_calls(data)
            # Chapter / global mode keeps single-shot + existing orchestrator outside
            if chapter_index is not None:
                return data, tool_calls, None
            if not tool_calls:
                break

            # Prefer startup tools; still allow listed legacy names
            safe_calls = [
                c
                for c in tool_calls
                if str(c.get("name") or "") in _STARTUP_TOOL_NAMES
            ] or tool_calls
            batch = self._tools.execute(book, user, safe_calls, chapter_index=chapter_index)
            executed_tools.extend(batch)
            for r in batch:
                if r.get("name") in {"search_references", "search_literature", "search_person_works"} and r.get("ok"):
                    payload = r.get("data") if isinstance(r.get("data"), dict) else {}
                    search_result = {
                        "ok": True,
                        "mode": payload.get("mode") or "user_query",
                        "search_type": payload.get("search_type")
                        or ("person_works" if r.get("name") == "search_person_works" else "literature"),
                        "raw_query": payload.get("raw_query") or "",
                        "queries": payload.get("queries") or payload.get("queries_used") or [],
                        "result": payload.get("result") if "result" in payload else payload,
                        "auto_ingested": False,
                        "progress": payload.get("progress") or [],
                        "summary": payload.get("summary") or "",
                    }
                # Merge suggest_book_settings into patch hints for the next model turn
                if r.get("name") == "suggest_book_settings" and r.get("ok"):
                    payload = r.get("data") if isinstance(r.get("data"), dict) else {}
                    sugg = payload.get("suggestions") if isinstance(payload.get("suggestions"), dict) else {}
                    if sugg and not _as_dict(data.get("book_settings_patch")):
                        data["book_settings_patch"] = dict(sugg)
                    if payload.get("decisions") and not _as_list(data.get("setting_decisions")):
                        data["setting_decisions"] = list(payload["decisions"])

            compact = []
            for r in batch:
                compact.append(
                    {
                        "name": r.get("name"),
                        "ok": r.get("ok"),
                        "error": r.get("error"),
                        "data": r.get("data"),
                        "summary": (r.get("data") or {}).get("summary")
                        if isinstance(r.get("data"), dict)
                        else None,
                    }
                )
            tool_payload = json.dumps(compact, ensure_ascii=False)[:_TOOL_RESULT_CHARS]
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "assistant_message": data.get("assistant_message") or "",
                            "tool_calls": safe_calls,
                            "thinking_notes": data.get("thinking_notes") or [],
                        },
                        ensure_ascii=False,
                    )[:4000],
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"工具结果（第 {iteration + 1} 轮）：\n{tool_payload}\n\n"
                        "请基于真实工具结果继续。"
                        "若仍需工具，再次输出带 tool_calls 的 JSON；"
                        "若已足够，输出最终 JSON（tool_calls 为空），并解释结果、更新 book_settings_patch。"
                    ),
                }
            )
        else:
            # Hit max iterations with pending tools — force a finalization turn without tools
            messages.append(
                {
                    "role": "user",
                    "content": "已达到工具调用上限。请基于已有工具结果输出最终 JSON，tool_calls 必须为空。",
                }
            )
            raw = self.llm.chat_completion(
                messages,
                model=model,
                max_tokens=4000,
                temperature=0.4,
                disable_thinking=True,
            )
            data = self._parse_turn_response(raw)

        # If final response still asks for search_request without having searched, one more forced tool+reply
        leftover = self._normalize_tool_calls(data)
        if leftover and chapter_index is None:
            batch = self._tools.execute(book, user, leftover, chapter_index=chapter_index)
            executed_tools.extend(batch)
            for r in batch:
                if r.get("name") in {"search_references", "search_literature", "search_person_works"} and r.get("ok"):
                    payload = r.get("data") if isinstance(r.get("data"), dict) else {}
                    search_result = {
                        "ok": True,
                        "mode": payload.get("mode") or "user_query",
                        "search_type": payload.get("search_type") or "literature",
                        "raw_query": payload.get("raw_query") or "",
                        "queries": payload.get("queries") or [],
                        "result": payload.get("result") if "result" in payload else payload,
                        "auto_ingested": False,
                        "progress": payload.get("progress") or [],
                        "summary": payload.get("summary") or "",
                    }
            tool_payload = json.dumps(batch, ensure_ascii=False)[:_TOOL_RESULT_CHARS]
            messages.append({"role": "assistant", "content": json.dumps({"tool_calls": leftover}, ensure_ascii=False)[:2000]})
            messages.append(
                {
                    "role": "user",
                    "content": f"工具结果：\n{tool_payload}\n\n请输出最终 JSON，tool_calls 为空，并解释工具结果。",
                }
            )
            raw = self.llm.chat_completion(
                messages,
                model=model,
                max_tokens=4000,
                temperature=0.4,
                disable_thinking=True,
            )
            data = self._parse_turn_response(raw)

        return data, executed_tools, search_result

    def run_turn(
        self,
        book: Book,
        user: User,
        message: str,
        *,
        chapter_index: int | None = None,
        assistant_mode: str = "normal",
    ) -> dict[str, Any]:
        mode = (assistant_mode or "normal").strip() or "normal"
        if mode not in {"normal", "quick_fill"}:
            mode = "normal"
        message = (message or "").strip()
        if not message and mode != "quick_fill":
            raise ValueError("message required")
        if not message and mode == "quick_fill":
            message = "（用户触发快速补齐）"

        history_chars = self._compression.history_char_count(book.id)
        compressed = self._compression.compress_if_needed(book, user, history_chars=history_chars)

        before_snap = snapshot_settings(book) if mode == "quick_fill" else None
        basis = self._basis.get_draft_or_create(book)
        model = resolve_assistant_model(user)

        if chapter_index is not None:
            # Keep chapter assistant on single-shot + legacy tool_calls (global prompt)
            raw = self.llm.chat_completion(
                [
                    {"role": "system", "content": self._system_prompt(chapter_index)},
                    {
                        "role": "user",
                        "content": self._build_user_prompt(
                            book, message, assistant_mode=mode, chapter_index=chapter_index
                        ),
                    },
                ],
                model=model,
                max_tokens=4000,
                temperature=0.4,
                disable_thinking=True,
            )
            data = self._parse_turn_response(raw)
            tool_calls = _as_list(data.get("tool_calls"))
            executed_tools = (
                self._tools.execute(book, user, tool_calls, chapter_index=chapter_index) if tool_calls else []
            )
            search_result = None
        else:
            data, executed_tools, search_result = self._run_startup_tool_loop(
                book,
                user,
                message=message,
                mode=mode,
                model=model,
                chapter_index=None,
            )

        # Merge suggestions from tool results if model forgot to copy into patch
        for r in executed_tools:
            if r.get("name") == "suggest_book_settings" and r.get("ok"):
                payload = r.get("data") if isinstance(r.get("data"), dict) else {}
                sugg = payload.get("suggestions") if isinstance(payload.get("suggestions"), dict) else {}
                patch = _as_dict(data.get("book_settings_patch"))
                if sugg:
                    merged = {**sugg, **{k: v for k, v in patch.items() if v is not None}}
                    data["book_settings_patch"] = merged
                if payload.get("decisions") and not _as_list(data.get("setting_decisions")):
                    data["setting_decisions"] = list(payload["decisions"])

        assistant_message = str(data.get("assistant_message") or "").strip()
        if not assistant_message:
            # Recover a minimal message from search/suggest tools
            for r in reversed(executed_tools):
                if r.get("ok") and isinstance(r.get("data"), dict) and r["data"].get("summary"):
                    assistant_message = str(r["data"]["summary"])
                    break
        if not assistant_message:
            raise RuntimeError("模型未返回有效内容，请稍后重试")

        setting_decisions = [x for x in _as_list(data.get("setting_decisions")) if isinstance(x, dict)]
        raw_patch = _as_dict(data.get("book_settings_patch"))
        filtered = _filter_patch_by_origins(
            book,
            {k: v for k, v in raw_patch.items() if v is not None},
            setting_decisions,
        )
        _apply_book_settings_patch(book, filtered, setting_decisions=setting_decisions)
        assistant_message = _ensure_user_facing_update_message(
            assistant_message, filtered, setting_decisions
        )

        extracted = _apply_extracted_requirements(
            self.db, book, _as_list(data.get("extracted_requirements"))
        )
        outline_route = _persist_outline_route(book, _as_dict(data.get("outline_route")) or None)
        file_judgements = [x for x in _as_list(data.get("file_judgements")) if isinstance(x, dict)][:20]
        clarification = _as_dict(data.get("clarification"))

        _silent_sync_basis(book, basis)
        self.db.flush()

        turn_meta = {
            "book_settings_patch": filtered,
            "setting_decisions": setting_decisions,
            "assistant_mode": mode,
            "tool_iterations": len(executed_tools),
        }
        if search_result:
            turn_meta["search_result"] = _compact_search_result(search_result)
        turn = AssistantTurn(
            book_id=book.id,
            user_message=("[quick_fill]" if mode == "quick_fill" else message),
            assistant_message=assistant_message,
            basis_patch=turn_meta,
            tool_calls=executed_tools or None,
        )
        self.db.add(turn)
        self.db.flush()

        settings = dict(book.ai_inferred_settings) if isinstance(book.ai_inferred_settings, dict) else {}
        if file_judgements:
            settings["file_judgements"] = file_judgements
        if setting_decisions:
            settings["last_setting_decisions"] = setting_decisions[:20]
        book.ai_inferred_settings = settings

        quick_fill_operation_id = None
        if mode == "quick_fill" and before_snap is not None:
            after_snap = snapshot_settings(book)
            quick_fill_operation_id = record_quick_fill(
                book, before=before_snap, after=after_snap, turn_id=str(turn.id)
            )

        traces_out: list[AssistantTrace] = []
        thinking_notes = [
            str(x).strip()
            for x in _as_list(data.get("thinking_notes"))
            if str(x).strip()
        ][:12]
        for note in thinking_notes:
            if any(
                token in note
                for token in (
                    "topic_brief",
                    "disciplines",
                    "topic_tags",
                    "book_settings",
                    "decision_type",
                    "book_type",
                    "style_type",
                    "[object Object]",
                )
            ):
                continue
            trace = AssistantTrace(
                turn_id=turn.id,
                claim=note[:500],
                evidence=None,
                reason_summary=None,
                confidence=None,
            )
            self.db.add(trace)
            traces_out.append(trace)
        # Surface search progress as light traces
        if search_result and isinstance(search_result.get("progress"), list):
            for step in search_result["progress"][:6]:
                if not isinstance(step, dict):
                    continue
                msg = str(step.get("message") or step.get("stage") or "").strip()
                if not msg:
                    continue
                trace = AssistantTrace(
                    turn_id=turn.id,
                    claim=msg[:500],
                    evidence=None,
                    reason_summary=None,
                    confidence=None,
                )
                self.db.add(trace)
                traces_out.append(trace)
        self.db.flush()

        refreshed = self._basis.get_draft(book.id) or basis
        pending_confirmations = [r for r in executed_tools if r.get("requires_confirmation")]
        open_q: list[str] = []
        if clarification.get("required") and clarification.get("question"):
            open_q.append(str(clarification["question"]).strip())

        return {
            "turn_id": turn.id,
            "assistant_message": assistant_message,
            "writing_basis": refreshed,
            "book_settings": current_book_settings(book),
            "setting_origins": get_setting_origins(book),
            "setting_decisions": setting_decisions,
            "extracted_requirements": extracted,
            "file_judgements": file_judgements,
            "outline_route": outline_route,
            "clarification": clarification,
            "search_result": search_result,
            "quick_fill_operation_id": quick_fill_operation_id,
            "traces": traces_out,
            "sources": self._sources.list_sources(book),
            "open_questions": open_q,
            "memories": self._memories.list_memories(book.id),
            "compressed_memories": compressed,
            "tool_results": executed_tools,
            "pending_confirmations": pending_confirmations,
            "confirmed_requirements": [
                {"category": r.category, "content": r.content, "strength": r.strength}
                for r in self.db.query(WritingRequirement)
                .filter(WritingRequirement.book_id == book.id, WritingRequirement.active.is_(True))
                .order_by(WritingRequirement.created_at.desc())
                .limit(30)
                .all()
            ],
        }

    def undo_quick_fill(self, book: Book, operation_id: str | None = None) -> dict[str, Any]:
        result = undo_quick_fill(book, operation_id)
        basis = self._basis.get_draft_or_create(book)
        _silent_sync_basis(book, basis)
        self.db.flush()
        return {
            **result,
            "book_settings": current_book_settings(book),
            "setting_origins": get_setting_origins(book),
        }

    def _system_prompt(self, chapter_index: int | None) -> str:
        if chapter_index is not None:
            from app.prompts.assistant.global_system import GLOBAL_ASSISTANT_SYSTEM

            return GLOBAL_ASSISTANT_SYSTEM
        return STARTUP_ASSISTANT_SYSTEM

    def list_turns(self, book_id: UUID, *, page: int = 1, page_size: int = 20) -> list[AssistantTurn]:
        offset = max(page - 1, 0) * page_size
        return (
            self.db.query(AssistantTurn)
            .filter(AssistantTurn.book_id == book_id)
            .order_by(AssistantTurn.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

    def list_turns_with_search(self, book_id: UUID, *, page: int = 1, page_size: int = 20) -> list[dict[str, Any]]:
        rows = self.list_turns(book_id, page=page, page_size=page_size)
        out: list[dict[str, Any]] = []
        for turn in rows:
            out.append(
                {
                    "id": turn.id,
                    "user_message": turn.user_message,
                    "assistant_message": turn.assistant_message,
                    "created_at": turn.created_at,
                    "search_result": extract_search_result_from_turn(turn),
                }
            )
        return out

    def list_traces(self, book_id: UUID, *, turn_id: UUID | None = None) -> list[AssistantTrace]:
        q = self.db.query(AssistantTrace).join(AssistantTurn, AssistantTrace.turn_id == AssistantTurn.id).filter(
            AssistantTurn.book_id == book_id
        )
        if turn_id:
            q = q.filter(AssistantTrace.turn_id == turn_id)
        return q.order_by(AssistantTrace.turn_id.desc()).all()
