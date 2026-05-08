import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import toast from "react-hot-toast";
import { ChevronRight, Sparkles, X } from "lucide-react";
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
import ChapterTiptapEditor, {
  type ChapterEditorHandle,
} from "@/components/editor/ChapterTiptapEditor";
import EditorSideTools, { type EditorTool } from "@/components/editor/EditorSideTools";
import EditorTopBar from "@/components/editor/EditorTopBar";
import OutlineNavBody from "@/components/editor/OutlineNavBody";
import type { OutlineSelection } from "@/components/editor/OutlineNavBody";
import OutlineReviewPanel from "@/components/editor/OutlineReviewPanel";
import RightPanel from "@/components/editor/RightPanel";
import SetupView from "@/components/editor/SetupView";
import { useAutoSave } from "@/hooks/useAutoSave";
import { useChapterStream } from "@/hooks/useChapterStream";
import { outlineConfirmed, phaseOf } from "@/lib/bookStatus";
import type { Chapter } from "@/types/chapter";
import type { OutlineChapter } from "@/types/outline";

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
  /** 左侧目录栏：工具栏切换显示；可点标题栏 × 关闭 */
  const [outlineSidebarOpen, setOutlineSidebarOpen] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [outlineBusy, setOutlineBusy] = useState(false);
  const [streamingIndex, setStreamingIndex] = useState<number | null>(null);
  const [autoGenerating, setAutoGenerating] = useState(false);
  /** 写作态章节顶栏：本章大纲默认一行，点击展开详情 */
  const [chapterOutlineExpanded, setChapterOutlineExpanded] = useState(false);

  const editorRef = useRef<ChapterEditorHandle>(null);
  const streamPlainRef = useRef("");
  const autoGenAbortRef = useRef(false);
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
    enabled: !!bookId && chapterIndex != null && phase === "WRITING",
  });

  const chapterDetail = chapterDetailQuery.data;

  const selectedMeta = useMemo(
    () => (selection.type === "chapter" ? chapters.find((c) => c.index === selection.index) ?? null : null),
    [chapters, selection],
  );

  useEffect(() => {
    setChapterOutlineExpanded(false);
  }, [chapterIndex]);

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

  async function invalidateAll(forChapterIndex?: number | null) {
    await qc.invalidateQueries({ queryKey: ["book", bookId] });
    await qc.invalidateQueries({ queryKey: ["outline", bookId] });
    const idx = forChapterIndex !== undefined && forChapterIndex !== null ? forChapterIndex : chapterIndex;
    if (idx != null) {
      await qc.invalidateQueries({ queryKey: ["chapter", bookId, idx] });
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
      setSelection({ type: "outline_preview" });
      toast.success("大纲已生成");
    } catch (e) {
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
      toast.error("大纲生成失败");
    } finally {
      setOutlineBusy(false);
      await qc.invalidateQueries({ queryKey: ["book", bookId] });
      await qc.invalidateQueries({ queryKey: ["outline", bookId] });
    }
  }

  async function startAutoGenerate(chaptersToGenerate: OutlineChapter[]) {
    if (autoGenerating) return;
    setAutoGenerating(true);
    autoGenAbortRef.current = false;

    const pending = chaptersToGenerate.filter(
      (c) =>
        c.status === "pending" &&
        !chapterHasBody(qc.getQueryData<Chapter>(["chapter", bookId!, c.index])),
    );

    for (const ch of pending) {
      if (autoGenAbortRef.current) break;
      setStreamingIndex(ch.index);
      setSelection({ type: "chapter", index: ch.index });

      await new Promise<void>((resolve) => {
        streamPlainRef.current = "";
        requestAnimationFrame(() => {
          editorRef.current?.clear();
          startStream(bookId!, ch.index, {
            onToken: appendStreamToken,
            onDone: async () => {
              setStreamingIndex(null);
              finalizeStreamPlainMarkdown();
              await persistEditorChapterToServer(ch.index);
              await invalidateAll(ch.index);
              resolve();
            },
            onError: (e) => {
              setStreamingIndex(null);
              toast.error(`第${ch.index}章生成失败：${e.message}`);
              resolve();
            },
          });
        });
      });

      await new Promise((r) => setTimeout(r, 500));
    }

    setAutoGenerating(false);
  }

  async function handleStartWriting() {
    if (!bookId) return;
    await putOutline(bookId, { chapters: [], confirm_start_writing: true });
    await invalidateAll();
    const nextOutline = await getOutline(bookId);
    const first = nextOutline.chapters[0];
    if (first) setSelection({ type: "chapter", index: first.index });
    toast.success("已进入写作阶段，开始自动生成…");
    setTimeout(() => {
      void startAutoGenerate(nextOutline.chapters);
    }, 800);
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
          await invalidateAll(idx);
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
        if (phase === "WRITING" && mode === "ai") {
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
                await invalidateAll(ch.index);
              },
              onError: (e) => {
                setStreamingIndex(null);
                toast.error(e.message);
              },
            });
          });
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

  const auxPanelTrigger =
    typeof document !== "undefined" && panelCollapsed
      ? createPortal(
          <button
            type="button"
            className="editor-aux-panel-trigger"
            onClick={() => setPanelCollapsed(false)}
            title="打开辅助面板"
            aria-label="打开辅助面板"
          >
            <Sparkles className="h-5 w-5" aria-hidden />
          </button>,
          document.body,
        )
      : null;

  return (
    <>
    <section className="page-transition-in">
      <div className="editor-page-outer p-4 sm:p-5">
        <div className="editor-page-root flex flex-col gap-2">
          <div className="editor-topbar-sticky">
            <div className="flex shrink-0 items-start gap-3">
              <div className="min-w-0 flex-1">
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
              </div>
              {autoGenerating ? (
                <button
                  type="button"
                  className="btn-secondary mt-1 h-8 shrink-0 px-3 text-xs"
                  onClick={() => {
                    autoGenAbortRef.current = true;
                    setAutoGenerating(false);
                  }}
                >
                  停止自动生成
                </button>
              ) : null}
            </div>
          </div>

          <div className="editor-workspace-row relative flex gap-2 items-start">
            <div className="editor-side-sticky flex shrink-0 items-start gap-3">
              <EditorSideTools
                active={tool}
                outlineOpen={outlineSidebarOpen}
                onOutlineToggle={() => setOutlineSidebarOpen((v) => !v)}
                outlineChapterCount={chapters.length}
                onChange={(t) => {
                  setTool(t);
                  setPanelCollapsed(false);
                }}
              />

              {outlineSidebarOpen ? (
                <aside className="editor-outline-sidebar" aria-label="目录栏">
                  <div className="editor-outline-sidebar-header">
                    <span className="text-sm font-semibold text-ink">目录</span>
                    <button
                      type="button"
                      className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                      title="隐藏目录"
                      aria-label="隐藏目录"
                      onClick={() => setOutlineSidebarOpen(false)}
                    >
                      <X className="h-4 w-4" aria-hidden />
                    </button>
                  </div>
                  <div className="editor-outline-sidebar-body">
                    <OutlineNavBody
                      chapters={chapters}
                      selection={selection}
                      onSelect={setSelection}
                      onReorder={handleReorder}
                      onRename={handleRenameChapter}
                      onRegenerate={handleRegenerateChapter}
                      onDelete={handleDeleteChapter}
                      onAddChapter={() => setAddOpen(true)}
                      dragDisabled={dragDisabled}
                      showOutlinePreviewNav={phase === "SETUP" && chapters.length > 0}
                    />
                  </div>
                </aside>
              ) : null}
            </div>

            <main className="editor-center-natural card min-w-0 flex-1 border border-slate-200/90 bg-white/85 shadow-[0_18px_40px_rgba(20,30,50,0.06)] backdrop-blur-md p-4 sm:p-5">
                {phase === "SETUP" && (
                  <>
                    {chapters.length === 0 ? (
                      <SetupView
                        book={book}
                        onBookPatched={(b) => qc.setQueryData(["book", bookId], b)}
                        onGenerateOutline={handleGenerateOutline}
                        generating={outlineGeneratingUi}
                        outlineLocked={false}
                      />
                    ) : outline && selection.type === "outline_preview" ? (
                      <OutlineReviewPanel
                        bookId={bookId}
                        targetAudience={book.target_audience}
                        outline={outline}
                        generating={outlineGeneratingUi}
                        onOutlinePatched={() => void invalidateAll()}
                        onStartWriting={() => void handleStartWriting()}
                        onRegenerateOutline={handleGenerateOutline}
                        onDeleteChapter={handleDeleteChapter}
                      />
                    ) : outline ? (
                      <SetupView
                        book={book}
                        onBookPatched={(b) => qc.setQueryData(["book", bookId], b)}
                        onGenerateOutline={handleGenerateOutline}
                        generating={outlineGeneratingUi}
                        outlineLocked={false}
                      />
                    ) : null}
                  </>
                )}

                {phase === "WRITING" && selection.type === "chapter" && (
                  <>
                    {chapterDetailQuery.isLoading && (
                      <p className="text-sm text-slate-500">加载章节正文…</p>
                    )}
                    {chapterDetail && !chapterDetailQuery.isLoading && (
                      <>
                        {selectedMeta && (
                          <div className="mb-5 border-b border-slate-100 pb-4">
                            <div className="flex items-center gap-3">
                              <button
                                type="button"
                                className="flex min-w-0 flex-1 items-center gap-2 rounded-lg py-1 text-left hover:bg-slate-50/80"
                                onClick={() => setChapterOutlineExpanded((v) => !v)}
                              >
                                <ChevronRight
                                  className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${chapterOutlineExpanded ? "rotate-90" : ""}`}
                                />
                                <span className="shrink-0 text-xs font-semibold uppercase tracking-wide text-violet-600">
                                  本章要点
                                </span>
                                {!chapterOutlineExpanded && (
                                  <span className="truncate text-sm text-slate-600">{chapterOutlinePreview}</span>
                                )}
                              </button>
                              {autoGenerating && streamingIndex === chapterIndex && (
                                <span className="animate-pulse text-xs text-violet-500">AI 生成中…</span>
                              )}
                              {autoGenerating && streamingIndex !== chapterIndex && (
                                <span className="text-xs text-slate-400">排队中</span>
                              )}
                              {nextChapterIndex != null && selectedMeta?.status === "done" && !autoGenerating && (
                                <button
                                  type="button"
                                  className="btn-next-chapter shrink-0 text-sm"
                                  onClick={() => setSelection({ type: "chapter", index: nextChapterIndex })}
                                >
                                  下一章 →
                                </button>
                              )}
                            </div>
                            {chapterOutlineExpanded && (
                              <div className="mt-3 space-y-2 border-t border-slate-50 pt-3 pl-6">
                                <p className="text-sm text-slate-700">
                                  <span className="font-medium text-slate-600">摘要：</span>
                                  {selectedMeta.summary?.trim() || "—"}
                                </p>
                                {(selectedMeta.key_points?.length ?? 0) > 0 && (
                                  <ul className="list-disc space-y-1 pl-4 text-xs text-slate-600">
                                    {selectedMeta.key_points.map((k) => (
                                      <li key={k}>{k}</li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            )}
                          </div>
                        )}

                        {streamingIndex === chapterIndex || chapterHasBody(chapterDetail) || autoGenerating ? (
                          <ChapterTiptapEditor
                            ref={editorRef}
                            key={chapterDetail.id}
                            chapter={chapterDetail}
                            readOnly={streamingIndex === chapterIndex}
                            onChange={(p) =>
                              scheduleSave(async () => {
                                const prev = (chapterDetail.content ?? {}) as Record<string, unknown>;
                                await updateChapter(bookId!, chapterIndex!, {
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
                        ) : (
                          <div className="flex min-h-[300px] items-center justify-center text-sm text-slate-400">
                            {autoGenerating ? (
                              "等待自动生成…"
                            ) : (
                              <div className="text-center">
                                <p className="mb-4">本章暂无正文</p>
                                <button
                                  type="button"
                                  className="btn-primary text-sm"
                                  onClick={() => void handleRegenerateChapter(chapterIndex!)}
                                >
                                  手动生成本章
                                </button>
                              </div>
                            )}
                          </div>
                        )}

                        {allDone && !autoGenerating && (
                          <div className="mt-8 flex justify-end border-t border-slate-100 pt-6">
                            <button type="button" className="btn-primary" onClick={() => void handleCompleteBook()}>
                              完成全书
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </>
                )}

                {phase === "WRITING" && selection.type === "setup" && (
                  <SetupView
                    book={book}
                    onBookPatched={(b) => qc.setQueryData(["book", bookId], b)}
                    onGenerateOutline={handleGenerateOutline}
                    generating={outlineGeneratingUi}
                    outlineLocked={outlineConfirmed(book)}
                  />
                )}
            </main>

            {!panelCollapsed ? (
              <div className="editor-side-sticky shrink-0">
                <RightPanel
                  tool={tool}
                  onClose={() => setPanelCollapsed(true)}
                  activeChapter={selectedMeta}
                  autoSaveStatus={saveStatus}
                  savedAt={savedAt}
                />
              </div>
            ) : null}
          </div>
        </div>

        <AddChapterDialog open={addOpen} onClose={() => setAddOpen(false)} onChoose={handleAddChapterChoice} />
      </div>
    </section>
    {auxPanelTrigger}
    </>
  );
}
