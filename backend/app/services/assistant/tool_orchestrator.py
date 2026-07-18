"""Stage 5/6 tool routing for global assistant."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.providers import resolve_assistant_model
from app.models.book import Book
from app.models.user import User
from app.prompts.assistant.topic_proposal import (
    TOPIC_PROPOSAL_SYSTEM,
    build_topic_proposal_user_prompt,
    format_topics_preview,
    parse_topic_proposal,
)
from app.services.assistant.book_settings_context import assess_outline_sources, current_book_settings
from app.services.assistant.external_search_service import ExternalSearchService
from app.services.assistant.project_memory_service import ProjectMemoryService
from app.services.assistant.search_intent_service import prepare_search, refine_search_intent, refine_search_queries
from app.services.assistant.source_retrieve_service import retrieve_source_context
from app.services.assistant.suggest_book_settings import suggest_book_settings
from app.services.assistant.workbook_service import inspect_workbook, read_sheet_range
from app.services.figure_service import get_chapter_figures
from app.services.literature_search_service import LiteratureSearchService
from app.services.outline_text import serialize_book_outline_markdown
from app.services.review.review_workspace_service import ReviewWorkspaceService
from app.services.sources.source_library_service import SourceLibraryService
from app.services.sources.source_outline_bridge import confirm_source_usage, prepare_outline_context
from app.services.writing.writing_basis_service import WritingBasisService


def _tool_result(
    name: str,
    *,
    ok: bool,
    panel_hint: str = "",
    data: dict | None = None,
    requires_confirmation: bool = False,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "panel_hint": panel_hint,
        "data": data or {},
        "requires_confirmation": requires_confirmation,
        "error": error,
    }


class ToolOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self._sources = SourceLibraryService(db)
        self._basis = WritingBasisService(db)
        self._memories = ProjectMemoryService(db)
        self._literature = LiteratureSearchService(db)
        self._review = ReviewWorkspaceService(db)
        self._external = ExternalSearchService()
        self._llm = LLMClient()

    def execute(
        self,
        book: Book,
        user: User,
        tool_calls: list[dict[str, Any]],
        *,
        chapter_index: int | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        last_search: dict[str, Any] | None = None
        last_prepare: dict[str, Any] | None = None
        for call in tool_calls:
            name = str(call.get("name") or "").strip()
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            try:
                if name == "patch_writing_basis":
                    basis = self._basis.get_draft_or_create(book)
                    patch = {k: v for k, v in args.items() if v is not None}
                    self._basis.patch(basis, patch)
                    results.append(_tool_result(name, ok=True, panel_hint="basis"))
                elif name == "add_pasted_source":
                    text = str(args.get("text") or "").strip()
                    if not text:
                        raise ValueError("text required")
                    item = self._sources.add_pasted_text(book, text)
                    results.append(
                        _tool_result(name, ok=True, panel_hint="sources", data={"source_id": str(item.id)})
                    )
                elif name == "list_sources":
                    results.append(
                        _tool_result(name, ok=True, panel_hint="sources", data={"sources": self._sources.list_sources(book)})
                    )
                elif name in {"prepare_search", "refine_search_intent", "refine_search_queries"}:
                    raw = str(
                        args.get("raw_query")
                        or args.get("query")
                        or args.get("person_name")
                        or ""
                    ).strip()
                    hint = str(args.get("search_type") or args.get("search_type_hint") or "").strip() or None
                    model = resolve_assistant_model(user)
                    if name == "refine_search_intent":
                        if not raw:
                            raise ValueError("raw_query required")
                        intent = refine_search_intent(raw, search_type_hint=hint, model=model)
                        data = {"intent": intent.to_dict(), "queries": []}
                        last_prepare = data
                        results.append(_tool_result(name, ok=True, panel_hint="sources", data=data))
                    elif name == "refine_search_queries":
                        intent_arg = args.get("intent") if isinstance(args.get("intent"), dict) else None
                        if intent_arg is None and last_prepare and last_prepare.get("intent"):
                            intent_arg = last_prepare["intent"]
                        if intent_arg is None and raw:
                            intent_arg = refine_search_intent(raw, search_type_hint=hint, model=model).to_dict()
                        if not intent_arg:
                            raise ValueError("intent or raw_query required")
                        queries = refine_search_queries(intent_arg, model=model)
                        data = {"intent": intent_arg, "queries": queries}
                        last_prepare = data
                        results.append(_tool_result(name, ok=True, panel_hint="sources", data=data))
                    else:
                        if not raw:
                            raise ValueError("raw_query required")
                        data = prepare_search(raw, search_type_hint=hint, model=model)
                        last_prepare = data
                        results.append(_tool_result(name, ok=True, panel_hint="sources", data=data))
                elif name == "search_person_works":
                    intent_arg = args.get("intent") if isinstance(args.get("intent"), dict) else None
                    queries_arg = args.get("queries") if isinstance(args.get("queries"), list) else None
                    if (intent_arg is None or not queries_arg) and last_prepare:
                        intent_arg = intent_arg or last_prepare.get("intent")
                        queries_arg = queries_arg or last_prepare.get("queries")
                    person = str(
                        args.get("person_name") or args.get("person") or args.get("query") or ""
                    ).strip()
                    if not person and isinstance(intent_arg, dict):
                        person = str(intent_arg.get("person_name") or intent_arg.get("display_query") or "").strip()
                    if not person and not intent_arg:
                        raise ValueError("先调用 prepare_search，或提供 person_name / intent+queries")
                    data = self._external.search_person_works(
                        person,
                        institution=str(args.get("institution") or "").strip() or None,
                        topic=str(args.get("topic") or "").strip() or None,
                        role=str(args.get("role") or "").strip() or None,
                        query=str(args.get("query") or person).strip() or None,
                        selected_candidate_id=str(args.get("selected_candidate_id") or "").strip() or None,
                        intent=intent_arg,
                        queries=queries_arg,
                        prepare_if_missing=True,
                    )
                    last_search = data
                    cand_n = len(data.get("candidates") or [])
                    summary = (
                        f"检索到 {len(data.get('works') or [])} 条公开作品；"
                        f"候选身份 {cand_n} 个；"
                        f"方向线索 {len(data.get('research_directions') or [])} 条"
                    )
                    if data.get("needs_disambiguation"):
                        summary += "。请先确认作者身份后再继续选题。"
                    # 检索结果不自动入库；仅返回候选供用户筛选确认
                    results.append(
                        _tool_result(
                            name,
                            ok=True,
                            panel_hint="literature",
                            data={
                                **data,
                                "summary": summary,
                                "auto_ingested": False,
                                "preview_text": self._format_search_paste(data),
                            },
                        )
                    )
                elif name == "confirm_source_usage":
                    sid = str(args.get("segment_id") or "").strip()
                    usage = str(args.get("usage") or "").strip()
                    if not sid or not usage:
                        raise ValueError("segment_id and usage required")
                    data = confirm_source_usage(self.db, book, segment_id=UUID(sid), usage=usage)
                    self.db.flush()
                    results.append(_tool_result(name, ok=True, panel_hint="sources", data=data))
                elif name == "prepare_outline_context":
                    primary_ids = args.get("primary_ids") if isinstance(args.get("primary_ids"), list) else None
                    requirement_ids = (
                        args.get("requirement_ids") if isinstance(args.get("requirement_ids"), list) else None
                    )
                    reference_ids = (
                        args.get("reference_outline_ids")
                        if isinstance(args.get("reference_outline_ids"), list)
                        else None
                    )
                    data = prepare_outline_context(
                        self.db,
                        book,
                        mode=str(args.get("mode") or "generate"),
                        primary_segment_ids=[str(x) for x in primary_ids] if primary_ids is not None else None,
                        requirement_segment_ids=[str(x) for x in requirement_ids]
                        if requirement_ids is not None
                        else None,
                        reference_outline_ids=[str(x) for x in reference_ids] if reference_ids is not None else None,
                        manuscript_policy=str(args.get("manuscript_policy") or "omit"),
                        must_keep_chapter_titles=bool(args.get("must_keep_chapter_titles", True)),
                    )
                    self.db.flush()
                    results.append(_tool_result(name, ok=True, panel_hint="outline", data=data))
                elif name == "propose_book_topics":
                    search_data = last_search
                    if not search_data:
                        person = str(args.get("person_name") or args.get("person") or "").strip()
                        if person:
                            search_data = self._external.search_person_works(
                                person,
                                institution=str(args.get("institution") or "").strip() or None,
                                topic=str(args.get("topic") or "").strip() or None,
                            )
                    if not search_data:
                        raise ValueError("需要先 search_person_works 或提供 person_name")
                    model = resolve_assistant_model(user)
                    raw = self._llm.chat_completion(
                        [
                            {"role": "system", "content": TOPIC_PROPOSAL_SYSTEM},
                            {"role": "user", "content": build_topic_proposal_user_prompt(search_data)},
                        ],
                        model=model,
                        max_tokens=2000,
                        temperature=0.35,
                    )
                    proposal = parse_topic_proposal(raw)
                    preview = format_topics_preview(proposal)
                    results.append(
                        _tool_result(
                            name,
                            ok=True,
                            panel_hint="confirm",
                            data={
                                "preview": preview,
                                "proposal": proposal,
                                "search": search_data,
                            },
                            requires_confirmation=True,
                        )
                    )
                elif name == "apply_topic_to_basis":
                    topic_index = args.get("topic_index")
                    title = str(args.get("title") or "").strip()
                    rationale = str(args.get("rationale") or "").strip()
                    if topic_index is not None:
                        try:
                            idx = int(topic_index)
                        except (TypeError, ValueError) as exc:
                            raise ValueError("topic_index invalid") from exc
                        proposal = args.get("proposal") if isinstance(args.get("proposal"), dict) else {}
                        topics = proposal.get("topics") if isinstance(proposal.get("topics"), list) else []
                        if 0 <= idx < len(topics) and isinstance(topics[idx], dict):
                            title = str(topics[idx].get("title") or title).strip()
                            rationale = str(topics[idx].get("rationale") or rationale).strip()
                    if not title:
                        raise ValueError("title or topic_index required")
                    basis = self._basis.get_draft_or_create(book)
                    patch = {
                        "direction": title,
                        "book_promise": rationale or basis.book_promise,
                    }
                    audience = str(args.get("audience") or "").strip()
                    if audience:
                        patch["target_readers"] = audience
                    self._basis.patch(basis, patch)
                    self._memories.upsert_from_update(
                        book.id,
                        content=f"选定书稿主题：{title}",
                        memory_type="decision",
                        strength="must",
                        confirmed=True,
                    )
                    results.append(
                        _tool_result(
                            name,
                            ok=True,
                            panel_hint="basis",
                            data={"title": title, "rationale": rationale},
                        )
                    )
                elif name == "search_literature":
                    query = str(args.get("query") or "").strip()
                    queries_arg = args.get("queries") if isinstance(args.get("queries"), list) else None
                    if not query and last_prepare and last_prepare.get("queries"):
                        queries_arg = queries_arg or last_prepare.get("queries")
                        query = str((queries_arg or [""])[0] or "").strip()
                    if not query and not queries_arg:
                        raise ValueError("先 prepare_search，或提供 query / queries")
                    if queries_arg and not query:
                        query = str(queries_arg[0]).strip()
                    ch_idx = args.get("chapter_index", chapter_index)
                    ch_idx = int(ch_idx) if ch_idx is not None else None
                    data = self._literature.search(
                        book,
                        query=query,
                        queries=[str(q) for q in (queries_arg or []) if str(q).strip()][:8] or None,
                        chapter_index=ch_idx,
                        skip_refine=bool(queries_arg),
                    )
                    if queries_arg:
                        data = {**data, "queries_used": [str(q) for q in queries_arg if str(q).strip()][:8]}
                    results.append(_tool_result(name, ok=True, panel_hint="literature", data=data))
                elif name == "search_references":
                    data = self._search_references(
                        book,
                        user,
                        args,
                        chapter_index=chapter_index,
                        last_prepare=last_prepare,
                    )
                    if data.get("prepare"):
                        last_prepare = data["prepare"]
                    last_search = data.get("result") if isinstance(data.get("result"), dict) else data
                    results.append(_tool_result(name, ok=True, panel_hint="literature", data=data))
                elif name == "retrieve_source_context":
                    q = str(args.get("query") or "").strip()
                    if not q:
                        raise ValueError("query required")
                    sids = args.get("source_ids") if isinstance(args.get("source_ids"), list) else None
                    top_k = int(args.get("top_k") or 12)
                    data = retrieve_source_context(
                        self.db,
                        book,
                        query=q,
                        source_ids=[str(x) for x in sids] if sids else None,
                        top_k=top_k,
                    )
                    results.append(_tool_result(name, ok=True, panel_hint="sources", data=data))
                elif name == "inspect_workbook":
                    sid = str(args.get("source_id") or "").strip()
                    if not sid:
                        raise ValueError("source_id required")
                    data = inspect_workbook(self.db, book, source_id=sid)
                    results.append(_tool_result(name, ok=True, panel_hint="sources", data=data))
                elif name == "read_sheet_range":
                    sid = str(args.get("source_id") or "").strip()
                    sheet = str(args.get("sheet_name") or "").strip()
                    if not sid or not sheet:
                        raise ValueError("source_id and sheet_name required")
                    data = read_sheet_range(
                        self.db,
                        book,
                        source_id=sid,
                        sheet_name=sheet,
                        cell_range=str(args.get("cell_range") or "A1:N50"),
                    )
                    results.append(_tool_result(name, ok=True, panel_hint="sources", data=data))
                elif name == "suggest_book_settings":
                    model = resolve_assistant_model(user)
                    fields = args.get("fields_to_complete")
                    fields_list = [str(x) for x in fields] if isinstance(fields, list) else None
                    sids = args.get("relevant_source_ids")
                    sid_list = [str(x) for x in sids] if isinstance(sids, list) else None
                    data = suggest_book_settings(
                        self.db,
                        book,
                        model=model,
                        fields_to_complete=fields_list,
                        relevant_source_ids=sid_list,
                        mode=str(args.get("mode") or "quick_fill"),
                    )
                    results.append(
                        _tool_result(
                            name,
                            ok=True,
                            panel_hint="basis",
                            data={
                                **data,
                                "current_book_settings": current_book_settings(book),
                            },
                        )
                    )
                elif name == "assess_outline_sources":
                    sids = args.get("source_ids") if isinstance(args.get("source_ids"), list) else None
                    data = assess_outline_sources(
                        self.db,
                        book,
                        source_ids=[str(x) for x in sids] if sids else None,
                    )
                    results.append(_tool_result(name, ok=True, panel_hint="outline", data=data))
                elif name == "run_review":
                    scope = str(args.get("scope") or "chapter").strip()
                    ch_idx = args.get("chapter_index", chapter_index)
                    ch_idx = int(ch_idx) if ch_idx is not None and scope == "chapter" else None
                    data = self._review.run_review(book, scope=scope, chapter_index=ch_idx, user=user)
                    hint = "review_workspace" if scope == "book" else "review"
                    results.append(_tool_result(name, ok=True, panel_hint=hint, data=data))
                elif name == "list_chapter_figures":
                    ch_idx = args.get("chapter_index", chapter_index)
                    if ch_idx is None:
                        raise ValueError("chapter_index required")
                    ch_idx = int(ch_idx)
                    figures = get_chapter_figures(book.id, ch_idx, self.db)
                    overview = [
                        {
                            "id": str(f.id),
                            "figure_number": f.figure_number,
                            "type": f.figure_type.value,
                            "status": f.status.value,
                            "caption": f.caption,
                            "chapter": f.chapter_index,
                        }
                        for f in figures
                    ]
                    results.append(
                        _tool_result(name, ok=True, panel_hint="refs", data={"chapter_index": ch_idx, "figures": overview})
                    )
                elif name == "update_project_understanding":
                    content = str(args.get("content") or "").strip()
                    if not content:
                        raise ValueError("content required")
                    row = self._memories.upsert_from_update(
                        book.id,
                        content=content,
                        memory_type=str(args.get("memory_type") or "fact"),
                        strength=str(args.get("strength") or "should"),
                        confirmed=bool(args.get("confirmed")),
                    )
                    results.append(
                        _tool_result(
                            name,
                            ok=True,
                            panel_hint="memory",
                            data={
                                "memory_id": str(row.id),
                                "content": row.content,
                                "memory_type": row.memory_type.value,
                            },
                        )
                    )
                elif name == "propose_outline_change":
                    instruction = str(args.get("instruction") or "").strip()
                    if not instruction:
                        raise ValueError("instruction required")
                    current = serialize_book_outline_markdown(book.id, self.db)
                    model = resolve_assistant_model(user)
                    preview = self._llm.chat_completion(
                        [
                            {
                                "role": "system",
                                "content": "你是大纲调整预览生成器。根据用户指令分析当前大纲，输出调整建议预览（不执行修改）。用中文条目列出变更。",
                            },
                            {
                                "role": "user",
                                "content": f"当前大纲：\n{current[:8000]}\n\n调整指令：{instruction}",
                            },
                        ],
                        model=model,
                        max_tokens=1500,
                        temperature=0.3,
                    )
                    results.append(
                        _tool_result(
                            name,
                            ok=True,
                            panel_hint="confirm",
                            data={"preview": preview.strip(), "instruction": instruction},
                            requires_confirmation=True,
                        )
                    )
                else:
                    results.append(_tool_result(name, ok=False, error="unknown tool"))
            except Exception as exc:
                results.append(_tool_result(name, ok=False, error=str(exc)))
        return results

    def _search_references(
        self,
        book: Book,
        user: User,
        args: dict[str, Any],
        *,
        chapter_index: int | None,
        last_prepare: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Business-level search: intent → queries → multi-source → return candidates (no ingest)."""
        mode = str(args.get("mode") or "user_query").strip() or "user_query"
        raw_query = str(args.get("raw_query") or args.get("query") or "").strip()
        progress: list[dict[str, Any]] = [{"stage": "intent", "message": "正在识别人物、机构和研究主题"}]

        if mode == "book_support" and not raw_query:
            bits = [
                book.title or "",
                book.topic_brief or "",
                " ".join(book.disciplines or []) if book.disciplines else (book.discipline or ""),
                " ".join(book.topic_tags or []) if book.topic_tags else "",
            ]
            raw_query = " ".join(b for b in bits if b).strip()[:500]
        if not raw_query:
            raise ValueError("raw_query required")

        model = resolve_assistant_model(user)
        hint = str(args.get("search_type") or "").strip() or None
        source_types = args.get("source_types") if isinstance(args.get("source_types"), list) else []
        if not hint and source_types:
            joined = " ".join(str(x) for x in source_types).lower()
            if "person" in joined or "作者" in joined:
                hint = "person_works"
        prepared = prepare_search(raw_query, search_type_hint=hint, model=model)
        intent = prepared.get("intent") or {}
        queries = list(prepared.get("queries") or [])
        progress.append(
            {
                "stage": "queries",
                "message": f"已生成 {len(queries)} 组查询",
                "queries": queries[:8],
            }
        )
        st = str(intent.get("search_type") or hint or "literature")
        ch_idx = args.get("chapter_index", chapter_index)
        ch_idx = int(ch_idx) if ch_idx is not None else None

        if st == "person_works":
            result = self._external.search_person_works(
                str(intent.get("person_name") or raw_query),
                intent=intent,
                queries=queries,
                prepare_if_missing=False,
            )
            progress.append(
                {
                    "stage": "completed",
                    "found": len(result.get("works") or []),
                    "candidates": len(result.get("candidates") or []),
                }
            )
            return {
                "mode": mode,
                "search_type": "person_works",
                "raw_query": raw_query,
                "queries": queries,
                "prepare": prepared,
                "progress": progress,
                "result": result,
                "auto_ingested": False,
                "summary": (
                    f"执行了 {len(queries) or 1} 组查询，作品 {len(result.get('works') or [])} 条，"
                    f"候选身份 {len(result.get('candidates') or [])} 个。结果未自动入库。"
                ),
            }

        lit = self._literature.search(
            book,
            query=raw_query,
            queries=queries or None,
            chapter_index=ch_idx,
            skip_refine=bool(queries),
        )
        items = lit.get("items") or lit.get("papers") or []
        progress.append({"stage": "completed", "remaining": len(items), "queries_run": len(queries) or 1})
        return {
            "mode": mode,
            "search_type": "literature",
            "raw_query": raw_query,
            "queries": queries or lit.get("refined_queries") or [],
            "prepare": prepared,
            "progress": progress,
            "result": lit,
            "auto_ingested": False,
            "summary": (
                f"执行了 {len(queries) or 1} 组查询，共返回 {len(items)} 条候选。"
                f"结果未自动入库，请用户筛选后加入资料库。"
            ),
        }

    @staticmethod
    def _format_search_paste(data: dict[str, Any]) -> str:
        lines = [
            f"【外部检索】{data.get('person')}",
            data.get("source_scope") or "",
            "",
            "研究方向：",
        ]
        for d in data.get("research_directions") or []:
            lines.append(f"- {d}")
        lines.append("")
        lines.append("代表性作品：")
        for w in (data.get("works") or [])[:15]:
            if not isinstance(w, dict):
                continue
            lines.append(f"- {w.get('title')} ({w.get('year') or '?'}) [{w.get('source')}]")
        warnings = data.get("warnings") or []
        if warnings:
            lines.append("")
            lines.append("注意：" + "；".join(str(x) for x in warnings))
        return "\n".join(lines)[:12000]
