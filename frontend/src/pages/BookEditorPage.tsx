import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import { ChevronRight, Sparkles } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { exportBook, getBook, updateBook } from "@/api/books";
import {
  createChapter,
  deleteChapter,
  getChapter,
  reorderChapters,
  updateChapter,
} from "@/api/chapters";
import { generateOutline, getOutline, putOutline } from "@/api/outline";
import AddChapterDialog from "@/components/editor/AddChapterDialog";
import ChapterDetailView from "@/components/editor/ChapterDetailView";
import ChapterTiptapEditor, {
  type ChapterEditorHandle,
} from "@/components/editor/ChapterTiptapEditor";
import EditorSideTools, { type EditorTool } from "@/components/editor/EditorSideTools";
import EditorTopBar from "@/components/editor/EditorTopBar";
import EmptyChapterState from "@/components/editor/EmptyChapterState";
import OutlinePopover from "@/components/editor/OutlinePopover";
import type { OutlineSelection } from "@/components/editor/OutlineNavBody";
import RightPanel from "@/components/editor/RightPanel";
import SetupView from "@/components/editor/SetupView";
import { useAutoSave } from "@/hooks/useAutoSave";
import { useChapterStream } from "@/hooks/useChapterStream";
import { outlineConfirmed, phaseOf } from "@/lib/bookStatus";
import type { Chapter } from "@/types/chapter";

function chapterHasBody(c: Chapter | undefined): boolean {
  if (!c?.content || typeof c.content !== "object") return false;
  const co = c.content as Record<string, unknown>;
  if (co.tiptap_json) return true;
  if (typeof co.text === "string" && co.text.trim().length > 0) return true;
  return false;
}

export default function BookEditorPage() {
  const { bookId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [selection, setSelection] = useState<OutlineSelection>({ type: "setup" });
  const [tool, setTool] = useState<EditorTool>("edit");
  const [panelCollapsed, setPanelCollapsed] = useState(true);
  const [outlinePopoverOpen, setOutlinePopoverOpen] = useState(false);
  const [chapterWriteStep, setChapterWriteStep] = useState<"outline" | "compose">("outline");
  const [addOpen, setAddOpen] = useState(false);
  const [outlineBusy, setOutlineBusy] = useState(false);
  const [streamingIndex, setStreamingIndex] = useState<number | null>(null);
  const [editorActive, setEditorActive] = useState(false);
  /** 写作态章节顶栏：本章大纲默认一行，点击展开详情 */
  const [chapterOutlineExpanded, setChapterOutlineExpanded] = useState(false);

  const editorRef = useRef<ChapterEditorHandle>(null);
  /** 流式生成全文缓冲，用于结束后一次性解析 ### / ** */
  const streamPlainRef = useRef("");
  const mainScrollRef = useRef<HTMLDivElement>(null);
  const { start: startStream } = useChapterStream();
  const { status: saveStatus, savedAt, scheduleSave } = useAutoSave();

  const bookQuery = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId!),
    enabled: !!bookId,
  });

  const outlineQuery = useQuery({
    queryKey: ["outline", bookId],
    queryFn: () => getOutline(bookId!),
    enabled: !!bookId,
  });

  const book = bookQuery.data;
  const outline = outlineQuery.data;
  const chapters = outline?.chapters ?? [];

  const phase = book ? phaseOf(book) : "SETUP";

  const chapterIndex = selection.type === "chapter" ? selection.index : null;

  const chapterDetailQuery = useQuery({
    queryKey: ["chapter", bookId, chapterIndex],
    queryFn: () => getChapter(bookId!, chapterIndex!),
    enabled: !!bookId && !!chapterIndex && phase === "WRITING",
  });

  const chapterDetail = chapterDetailQuery.data;

  const selectedMeta = useMemo(
    () => (selection.type === "chapter" ? chapters.find((c) => c.index === selection.index) ?? null : null),
    [chapters, selection],
  );

  useEffect(() => {
    setEditorActive(false);
    setChapterWriteStep("outline");
    setChapterOutlineExpanded(false);
  }, [chapterIndex]);

  useEffect(() => {
    if (chapterDetail && chapterHasBody(chapterDetail)) {
      setEditorActive(true);
    }
  }, [chapterDetail]);

  const currentWords = useMemo(
    () => chapters.reduce((s, c) => s + (c.word_count ?? 0), 0),
    [chapters],
  );

  const targetWords = book?.target_words ?? 80000;

  async function handleExport(format: "markdown" | "docx") {
    if (!bookId || !book) return;
    const toastId = toast.loading("正在导出…");
    try {
      const blob = await exportBook(bookId, format);
      const ext = format === "markdown" ? "md" : "docx";
      const safe =
        book.title
          .replace(/[<>:"/\\|?*\x00-\x1f]/g, "_")
          .trim()
          .slice(0, 80) || "book";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${safe}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("导出成功", { id: toastId });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "导出失败";
      toast.error(msg, { id: toastId });
    }
  }

  const nextChapterIndex = useMemo(() => {
    if (!selectedMeta) return null;
    const next = chapters.find((c) => c.index === selectedMeta.index + 1);
    return next?.index ?? null;
  }, [chapters, selectedMeta]);

  const chapterOutlinePreview = useMemo(() => {
    const s = selectedMeta?.summary?.trim();
    if (!s) return "暂无摘要，点击展开查看要点";
    return s.length > 80 ? `${s.slice(0, 80)}…` : s;
  }, [selectedMeta]);

  const allDone = chapters.length > 0 && chapters.every((c) => c.status === "done");

  function scrollEditorMainToTop() {
    mainScrollRef.current?.scrollTo({ top: 0, behavior: "auto" });
  }

  function appendStreamToken(t: string) {
    streamPlainRef.current += t;
    editorRef.current?.appendText(t);
  }

  function finalizeStreamPlainMarkdown() {
    const raw = streamPlainRef.current;
    streamPlainRef.current = "";
    if (raw.trim()) {
      editorRef.current?.applyPlainMarkdown(raw);
    }
  }

  async function persistEditorChapterToServer(chapterIdx: number) {
    if (!bookId) return;
    const payload = editorRef.current?.getSerialized();
    if (!payload) return;
    const cur = qc.getQueryData<Chapter>(["chapter", bookId, chapterIdx]);
    const prev = (cur?.content ?? {}) as Record<string, unknown>;
    const updated = await updateChapter(bookId, chapterIdx, {
      content: {
        ...prev,
        tiptap_json: payload.json,
        text: payload.text,
      },
    });
    qc.setQueryData(["chapter", bookId, chapterIdx], updated);
  }

  async function invalidateAll() {
    await qc.invalidateQueries({ queryKey: ["book", bookId] });
    await qc.invalidateQueries({ queryKey: ["outline", bookId] });
    if (chapterIndex) {
      await qc.invalidateQueries({ queryKey: ["chapter", bookId, chapterIndex] });
    }
  }

  const titleMutation = useMutation({
    mutationFn: (title: string) => updateBook(bookId!, { title }),
    onSuccess: (b) => {
      qc.setQueryData(["book", bookId], b);
      toast.success("书名已更新");
    },
  });

  const modelMutation = useMutation({
    mutationFn: (ai_model: string) => updateBook(bookId!, { ai_model }),
    onSuccess: (b) => qc.setQueryData(["book", bookId], b),
  });

  async function handleGenerateOutline(payload: { topic_override?: string | null; target_audience?: string | null }) {
    if (!bookId) return;
    setOutlineBusy(true);
    try {
      await generateOutline(bookId, payload);
      await invalidateAll();
      const nextOutline = await getOutline(bookId);
      const first = nextOutline.chapters[0]?.index ?? 1;
      setSelection({ type: "chapter", index: first });
      toast.success("大纲已生成");
    } catch (e) {
      // #region agent log
      const ax = axios.isAxiosError(e) ? e : null;
      fetch("http://127.0.0.1:7569/ingest/48306f0f-bede-4e99-ab8b-2ecb30de09e8", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "7c6f39" },
        body: JSON.stringify({
          sessionId: "7c6f39",
          location: "BookEditorPage.tsx:handleGenerateOutline",
          message: "generateOutline client error",
          data: {
            code: ax?.code,
            status: ax?.response?.status,
            isTimeout: ax?.code === "ECONNABORTED",
            detail: typeof ax?.response?.data === "object" ? JSON.stringify(ax?.response?.data) : String(ax?.response?.data ?? ""),
          },
          timestamp: Date.now(),
          hypothesisId: "H7",
        }),
      }).catch(() => {});
      // #endregion
      toast.error("大纲生成失败");
    } finally {
      setOutlineBusy(false);
      await qc.invalidateQueries({ queryKey: ["book", bookId] });
      await qc.invalidateQueries({ queryKey: ["outline", bookId] });
    }
  }

  async function handleStartWriting() {
    if (!bookId) return;
    await putOutline(bookId, { chapters: [], confirm_start_writing: true });
    await invalidateAll();
    setSelection({ type: "chapter", index: 1 });
    toast.success("已进入写作阶段");
  }

  async function handleReorder(items: { chapter_id: string; new_index: number }[]) {
    if (!bookId) return;
    await reorderChapters(bookId, items);
    await invalidateAll();
  }

  async function handleRenameChapter(idx: number, title: string) {
    if (!bookId) return;
    await updateChapter(bookId, idx, { title });
    await invalidateAll();
  }

  async function handleDeleteChapter(idx: number) {
    if (!bookId) return;
    if (!window.confirm("确定删除该章节？")) return;
    await deleteChapter(bookId, idx);
    await invalidateAll();
    setSelection((prev) => {
      if (prev.type === "chapter" && prev.index === idx) return { type: "setup" };
      return prev;
    });
    toast.success("已删除");
  }

  async function handleRegenerateChapter(idx: number) {
    if (!bookId) return;
    if (!window.confirm("将调用 AI 重新生成该章正文，确定？")) return;
    setEditorActive(true);
    setStreamingIndex(idx);
    requestAnimationFrame(() => {
      streamPlainRef.current = "";
      editorRef.current?.clear();
      startStream(bookId, idx, {
        onToken: appendStreamToken,
        onDone: async () => {
          setStreamingIndex(null);
          finalizeStreamPlainMarkdown();
          await persistEditorChapterToServer(idx);
          scrollEditorMainToTop();
          await invalidateAll();
          toast.success("本章生成完成");
        },
        onError: (e) => {
          setStreamingIndex(null);
          toast.error(e.message);
        },
      });
    });
  }

  function handleAddChapterChoice(mode: "ai" | "manual") {
    if (!bookId) return;
    setAddOpen(false);
    createChapter(bookId, { title: `新章节`, insert_at: null })
      .then(async (ch) => {
        await invalidateAll();
        setSelection({ type: "chapter", index: ch.index });
        if (phase === "WRITING") {
          setChapterWriteStep(mode === "manual" ? "outline" : "compose");
          setEditorActive(false);
          if (mode === "ai") {
            setStreamingIndex(ch.index);
            requestAnimationFrame(() => {
              streamPlainRef.current = "";
              editorRef.current?.clear();
              startStream(bookId, ch.index, {
                onToken: appendStreamToken,
                onDone: async () => {
                  setStreamingIndex(null);
                  finalizeStreamPlainMarkdown();
                  await persistEditorChapterToServer(ch.index);
                  scrollEditorMainToTop();
                  await invalidateAll();
                },
                onError: (e) => {
                  setStreamingIndex(null);
                  toast.error(e.message);
                },
              });
            });
          }
        }
      })
      .catch(async () => {
        toast.error("创建章节失败");
        await qc.invalidateQueries({ queryKey: ["book", bookId] });
        await qc.invalidateQueries({ queryKey: ["outline", bookId] });
      });
  }

  async function handleCompleteBook() {
    if (!bookId) return;
    await updateBook(bookId, { status: "completed" });
    await invalidateAll();
    toast.success("全书已完成（可在列表查看状态）");
  }

  const pendingNoBody =
    phase === "WRITING" &&
    !!chapterDetail &&
    !!selectedMeta &&
    selectedMeta.status === "pending" &&
    !chapterHasBody(chapterDetail) &&
    streamingIndex !== chapterIndex;

  const showChapterOutlineForm =
    selection.type === "chapter" &&
    phase === "WRITING" &&
    !!selectedMeta &&
    pendingNoBody &&
    chapterWriteStep === "outline";

  const showEmptyCompose =
    selection.type === "chapter" &&
    phase === "WRITING" &&
    !!chapterDetail &&
    pendingNoBody &&
    chapterWriteStep === "compose" &&
    !editorActive &&
    streamingIndex !== chapterIndex;

  const showWritingEditor =
    phase === "WRITING" &&
    selection.type === "chapter" &&
    chapterDetail &&
    (streamingIndex === chapterIndex ||
      chapterHasBody(chapterDetail) ||
      (pendingNoBody && chapterWriteStep === "compose" && editorActive));

  if (!bookId) {
    return (
      <div className="surface-panel">
        <p className="text-sm text-slate-600">无效路由</p>
      </div>
    );
  }

  if (bookQuery.isLoading || !book) {
    return <div className="surface-panel">加载书稿中…</div>;
  }

  if (!bookQuery.isLoading && !bookQuery.data) {
    return (
      <div className="surface-panel">
        <p className="text-sm text-slate-600">未找到该书稿。</p>
        <Link to="/app/books" className="mt-3 inline-flex text-sm text-brand hover:underline">
          返回图书管理
        </Link>
      </div>
    );
  }

  const dragDisabled = book.status === "outline_generating" || chapters.length === 0;

  const outlineGeneratingUi = outlineBusy || book.status === "outline_generating";

  return (
    <section className="page-transition-in">
      <div className="surface-panel flex max-h-[calc(100vh-4rem)] min-h-0 flex-col gap-5 overflow-hidden p-5 sm:p-6">
        <div className="editor-page-root flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
          <EditorTopBar
            title={book.title}
            currentWords={currentWords}
            targetWords={targetWords}
            aiModel={book.ai_model}
            onTitleSave={(t) => titleMutation.mutate(t)}
            onModelChange={(m) => modelMutation.mutate(m)}
            autoSaveStatus={saveStatus}
            savedAt={savedAt}
            onBack={() => navigate("/app/books")}
            onExport={handleExport}
          />

          <div className="editor-workspace-row relative flex min-h-0 flex-1 gap-3 overflow-hidden">
            <EditorSideTools
              active={tool}
              outlineOpen={outlinePopoverOpen}
              onOutlineToggle={() => setOutlinePopoverOpen((v) => !v)}
              outlineChapterCount={chapters.length}
              onChange={(t) => {
                setTool(t);
                setPanelCollapsed(false);
              }}
            />

            <main
              ref={mainScrollRef}
              className="editor-center card flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden border border-slate-200/90 bg-white/85 shadow-[0_18px_40px_rgba(20,30,50,0.06)] backdrop-blur-md"
            >
              <div className="editor-main-scroll min-h-0 flex-1 overflow-y-auto p-6">
          {selection.type === "setup" && (
            <SetupView
              book={book}
              onBookPatched={(b) => qc.setQueryData(["book", bookId], b)}
              onGenerateOutline={handleGenerateOutline}
              generating={outlineGeneratingUi}
              outlineLocked={outlineConfirmed(book)}
            />
          )}

          {selection.type === "chapter" && phase === "SETUP" && selectedMeta && (
            <ChapterDetailView
              bookId={bookId}
              chapter={selectedMeta}
              onPatched={() => invalidateAll()}
              onStartWriting={handleStartWriting}
              busy={outlineGeneratingUi}
            />
          )}

          {selection.type === "chapter" && phase === "WRITING" && chapterDetailQuery.isLoading && (
            <p className="text-sm text-slate-500">加载章节正文…</p>
          )}

          {selection.type === "chapter" && phase === "WRITING" && chapterDetail && !chapterDetailQuery.isLoading && (
            <>
              {showChapterOutlineForm && selectedMeta && (
                <ChapterDetailView
                  variant="chapter"
                  bookId={bookId}
                  chapter={selectedMeta}
                  onPatched={() => invalidateAll()}
                  onStartWriting={() => setChapterWriteStep("compose")}
                  busy={outlineGeneratingUi}
                />
              )}

              {showEmptyCompose && (
                <EmptyChapterState
                  onAiAssist={() => {
                    setEditorActive(true);
                    setStreamingIndex(chapterIndex!);
                    requestAnimationFrame(() => {
                      streamPlainRef.current = "";
                      editorRef.current?.clear();
                      startStream(bookId, chapterIndex!, {
                        onToken: appendStreamToken,
                        onDone: async () => {
                          setStreamingIndex(null);
                          finalizeStreamPlainMarkdown();
                          await persistEditorChapterToServer(chapterIndex!);
                          scrollEditorMainToTop();
                          await invalidateAll();
                          toast.success("生成完成");
                        },
                        onError: (e) => {
                          setStreamingIndex(null);
                          toast.error(e.message);
                        },
                      });
                    });
                  }}
                  onManual={() => setEditorActive(true)}
                />
              )}

              {showWritingEditor && (
                <>
                  {selectedMeta ? (
                    <div className="mb-5 border-b border-slate-100 pb-4">
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          className="flex min-w-0 flex-1 items-center gap-2 rounded-lg py-1 text-left transition hover:bg-slate-50/80"
                          onClick={() => setChapterOutlineExpanded((v) => !v)}
                          aria-expanded={chapterOutlineExpanded}
                        >
                          <ChevronRight
                            className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${chapterOutlineExpanded ? "rotate-90" : ""}`}
                            aria-hidden
                          />
                          <span className="shrink-0 text-xs font-semibold uppercase tracking-wide text-violet-600">
                            本章大纲要点
                          </span>
                          {!chapterOutlineExpanded ? (
                            <span className="truncate text-sm text-slate-600">{chapterOutlinePreview}</span>
                          ) : null}
                        </button>
                        {nextChapterIndex != null && selectedMeta?.status === "done" ? (
                          <button
                            type="button"
                            className="btn-next-chapter shrink-0 text-sm"
                            onClick={() => setSelection({ type: "chapter", index: nextChapterIndex })}
                          >
                            下一章 →
                          </button>
                        ) : null}
                      </div>
                      {chapterOutlineExpanded ? (
                        <div className="mt-3 space-y-2 border-t border-slate-50 pt-3 pl-6">
                          <p className="text-sm leading-relaxed text-slate-700">
                            <span className="font-medium text-slate-600">摘要：</span>
                            {selectedMeta.summary?.trim() || "—"}
                          </p>
                          {selectedMeta.key_points?.length ? (
                            <ul className="list-disc space-y-1 pl-4 text-xs text-slate-600">
                              {selectedMeta.key_points.map((k) => (
                                <li key={k}>{k}</li>
                              ))}
                            </ul>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  <ChapterTiptapEditor
                    ref={editorRef}
                    key={chapterDetail.id}
                    chapter={chapterDetail}
                    readOnly={streamingIndex === chapterIndex}
                    onChange={(p) =>
                      scheduleSave(async () => {
                        const prev = (chapterDetail.content ?? {}) as Record<string, unknown>;
                        await updateChapter(bookId, chapterIndex!, {
                          content: {
                            ...prev,
                            tiptap_json: p.json,
                            text: p.text,
                          },
                        });
                        await invalidateAll();
                      })
                    }
                  />

                  <div className="mt-8 flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pt-6">
                    {allDone ? (
                      <button type="button" className="btn-primary" onClick={() => handleCompleteBook()}>
                        完成全书
                      </button>
                    ) : null}
                  </div>
                </>
              )}
            </>
          )}
              </div>
            </main>

            {!panelCollapsed ? (
              <RightPanel
                tool={tool}
                onClose={() => setPanelCollapsed(true)}
                activeChapter={selectedMeta}
                autoSaveStatus={saveStatus}
                savedAt={savedAt}
              />
            ) : null}
          </div>

          {panelCollapsed ? (
            <button
              type="button"
              className="editor-panel-fab"
              onClick={() => setPanelCollapsed(false)}
              title="打开辅助面板"
              aria-label="打开辅助面板"
            >
              <Sparkles className="h-5 w-5" aria-hidden />
            </button>
          ) : null}
        </div>

        <OutlinePopover
          open={outlinePopoverOpen}
          onClose={() => setOutlinePopoverOpen(false)}
          chapters={chapters}
          selection={selection}
          onSelect={setSelection}
          onReorder={handleReorder}
          onRename={handleRenameChapter}
          onRegenerate={handleRegenerateChapter}
          onDelete={handleDeleteChapter}
          onAddChapter={() => setAddOpen(true)}
          dragDisabled={dragDisabled}
        />

        <AddChapterDialog open={addOpen} onClose={() => setAddOpen(false)} onChoose={handleAddChapterChoice} />
      </div>
    </section>
  );
}
