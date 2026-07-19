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
from app.services.assistant.external_search_service import ExternalSearchService
from app.services.assistant.project_memory_service import ProjectMemoryService
from app.services.figure_service import get_chapter_figures
from app.services.literature_search_service import LiteratureSearchService
from app.services.outline_text import serialize_book_outline_markdown
from app.services.review.review_workspace_service import ReviewWorkspaceService
from app.services.sources.source_library_service import SourceLibraryService
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
                elif name == "search_person_works":
                    person = str(args.get("person_name") or args.get("person") or "").strip()
                    if not person:
                        raise ValueError("person_name required")
                    data = self._external.search_person_works(
                        person,
                        institution=str(args.get("institution") or "").strip() or None,
                        topic=str(args.get("topic") or "").strip() or None,
                    )
                    last_search = data
                    summary = (
                        f"检索到 {len(data.get('works') or [])} 条公开作品；"
                        f"方向线索 {len(data.get('research_directions') or [])} 条"
                    )
                    paste = self._format_search_paste(data)
                    source_item = self._sources.add_pasted_text(book, paste)
                    results.append(
                        _tool_result(
                            name,
                            ok=True,
                            panel_hint="sources",
                            data={**data, "summary": summary, "source_id": str(source_item.id)},
                        )
                    )
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
                    if not query:
                        raise ValueError("query required")
                    ch_idx = args.get("chapter_index", chapter_index)
                    ch_idx = int(ch_idx) if ch_idx is not None else None
                    data = self._literature.search(book, query=query, chapter_index=ch_idx)
                    results.append(_tool_result(name, ok=True, panel_hint="literature", data=data))
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
