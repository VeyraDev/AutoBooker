import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import toast from "react-hot-toast";
import { Link, useNavigate, useParams } from "react-router-dom";

import { exportBook, getBook, updateBook } from "@/api/books";
import { createChapter, deleteChapter, getChapter, reorderChapters, updateChapter } from "@/api/chapters";
import { generateOutline, getOutline, putOutline } from "@/api/outline";
import AddChapterDialog from "@/components/editor/AddChapterDialog";
import type { AddChapterFormValues } from "@/components/editor/AddChapterDialog";
import BookSettingsModal from "@/components/editor/BookSettingsModal";
import ChapterTiptapEditor, { type ChapterEditorHandle } from "@/components/editor/ChapterTiptapEditor";
import EditorTopBar from "@/components/editor/EditorTopBar";
import OutlineDrawer from "@/components/editor/OutlineDrawer";
import OutlineReviewPanel from "@/components/editor/OutlineReviewPanel";
import OutlineNavBody from "@/components/editor/OutlineNavBody";
import type { OutlineSelection } from "@/components/editor/OutlineNavBody";
import PlanningWizard from "@/components/editor/PlanningWizard";
import RightPanel, { AuxPanelFab, type RightPanelTab } from "@/components/editor/RightPanel";
import { topicKey } from "@/components/editor/SetupView";
import { getChapterGenMode, setChapterGenMode, type ChapterGenMode } from "@/lib/chapterGenMode";
import { useAutoSave } from "@/hooks/useAutoSave";
import { useChapterStream } from "@/hooks/useChapterStream";
import { useDailyWordDelta } from "@/hooks/useDailyWordDelta";
import { phaseOf } from "@/lib/bookStatus";
import { plainTextMarkdownToTiptapDoc, shouldParseAsMarkdown } from "@/lib/plainTextMarkdownToTiptap";
import type { Chapter } from "@/types/chapter";
import type { OutlineChapter, OutlineChapterPatch } from "@/types/outline";

function chapterHasBody(c: Chapter | undefined): boolean {
  if (!c?.content || typeof c.content !== "object") return false;
  const co = c.content as Record<string, unknown>;
  if (co.tiptap_json) return true;
  if (typeof co.text === "string" && co.text.trim().length > 0) return true;
  return false;
}

function streamRawToChapterPayload(raw: string): { json: Record<string, unknown>; text: string } {
  const trimmed = raw.trim();
  if (!trimmed) {
    return { json: { type: "doc", content: [] }, text: "" };
  }
  if (shouldParseAsMarkdown(raw)) {
    return { json: plainTextMarkdownToTiptapDoc(raw), text: raw };
  }
  return {
    json: {
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "text", text: raw }] }],
    },
    text: raw,
  };
}

export default function BookEditorPage() {
  const { bookId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [selection, setSelection] = useState<OutlineSelection>({ type: "chapter", index: 1 });
  const [panelCollapsed, setPanelCollapsed] = useState(true);
  const [outlineRailExpanded, setOutlineRailExpanded] = useState(true);
  const [outlineRailTip, setOutlineRailTip] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [outlineBusy, setOutlineBusy] = useState(false);
  const [streamingIndex, setStreamingIndex] = useState<number | null>(null);
  const [autoGenerating, setAutoGenerating] = useState(false);
  const [autoGenSlot, setAutoGenSlot] = useState<{ current: number; total: number } | null>(null);
  const [autoGenPaused, setAutoGenPaused] = useState(false);
  const [outlineDrawerOpen, setOutlineDrawerOpen] = useState(false);
  const [dailyWordsTick, setDailyWordsTick] = useState(0);
  const [panelTab, setPanelTab] = useState<RightPanelTab>("detail");
  const [assistantSeed, setAssistantSeed] = useState("");
  const [bookSettingsModalOpen, setBookSettingsModalOpen] = useState(false);

  const editorRef = useRef<ChapterEditorHandle>(null);
  const editorMainScrollRef = useRef<HTMLDivElement>(null);
  const streamPlainRef = useRef("");
  const autoGenAbortRef = useRef(false);
  const chapterIndexRef = useRef<number | null>(null);
  const streamingIndexRef = useRef<number | null>(null);
  const prevChapterIndexNavRef = useRef<number | null>(null);
  const { start: startStream } = useChapterStream();
  const { status: saveStatus, savedAt, scheduleSave } = useAutoSave();
  const { recordChars } = useDailyWordDelta(bookId);

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
    enabled: !!bookId && chapterIndex != null && (phase === "WRITING" || phase === "COMPLETED"),
  });

  const chapterDetail = chapterDetailQuery.data;

  const [liveChapterChars, setLiveChapterChars] = useState<number | null>(null);

  useEffect(() => {
    if (!chapterDetail) {
      setLiveChapterChars(null);
      return;
    }
    const co = chapterDetail.content as Record<string, unknown> | null | undefined;
    const text = typeof co?.text === "string" ? co.text : "";
    setLiveChapterChars(text.length);
  }, [chapterDetail?.id, chapterDetail]);

  const selectedMeta = useMemo(
    () => (selection.type === "chapter" ? chapters.find((c) => c.index === selection.index) ?? null : null),
    [chapters, selection],
  );

  useEffect(() => {
    if ((phase !== "WRITING" && phase !== "COMPLETED") || chapters.length === 0) return;
    const ok =
      selection.type === "chapter" && chapters.some((c) => c.index === selection.index);
    if (!ok) {
      setSelection({ type: "chapter", index: chapters[0].index });
    }
  }, [phase, chapters, selection]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "\\") {
        e.preventDefault();
        setOutlineRailExpanded((v) => !v);
        setPanelCollapsed((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    chapterIndexRef.current = chapterIndex;
  }, [chapterIndex]);

  useEffect(() => {
    streamingIndexRef.current = streamingIndex;
  }, [streamingIndex]);

  /** 切换章节后整页滚回顶部（整页文档滚动） */
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
    editorMainScrollRef.current?.scrollTo?.({ top: 0, behavior: "auto" });
  }, [chapterDetail?.id]);

  /** 切回正在生成的章节时，用已累计的正文一次性对齐编辑器 */
  useEffect(() => {
    const prev = prevChapterIndexNavRef.current;
    prevChapterIndexNavRef.current = chapterIndex;
    if (chapterIndex == null || streamingIndex == null) return;
    if (chapterIndex !== streamingIndex) return;
    if (prev === chapterIndex) return;
    const plain = streamPlainRef.current;
    if (!plain.trim()) return;
    requestAnimationFrame(() => {
      editorRef.current?.applyPlainMarkdown(plain);
    });
  }, [chapterIndex, streamingIndex]);

  const currentWords = useMemo(() => chapters.reduce((s, c) => s + (c.word_count ?? 0), 0), [chapters]);

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

  const allDone = chapters.length > 0 && chapters.every((c) => c.status === "done");

  const chapterGenMode = bookId ? getChapterGenMode(bookId) : "auto";

  const prevChapterIndex = useMemo(() => {
    if (!selectedMeta) return null;
    const sorted = [...chapters].sort((a, b) => a.index - b.index);
    const i = sorted.findIndex((c) => c.index === selectedMeta.index);
    if (i <= 0) return null;
    return sorted[i - 1]?.index ?? null;
  }, [chapters, selectedMeta]);

  const pendingChapterCount = useMemo(() => chapters.filter((c) => c.status === "pending").length, [chapters]);

  const chapterNavPrimary = useMemo(() => {
    if (chapterIndex == null || !selectedMeta) return null;
    const streamingHere = streamingIndex === chapterIndex;
    if (selectedMeta.status === "done") {
      return { label: "↺ 重新生成" as const, disabled: false };
    }
    if (streamingHere || selectedMeta.status === "generating") {
      return { label: "生成中…" as const, disabled: true };
    }
    if (selectedMeta.status === "pending") {
      if (chapterGenMode === "auto" && autoGenerating && streamingIndex != null && streamingIndex !== chapterIndex) {
        return { label: "等待中" as const, disabled: true };
      }
      return { label: "▶ 生成本章" as const, disabled: false };
    }
    return { label: "↺ 重新生成" as const, disabled: false };
  }, [chapterIndex, selectedMeta, streamingIndex, chapterGenMode, autoGenerating]);

  const todayWords = useMemo(() => {
    if (!bookId) return 0;
    try {
      const key = `autobooker_daily_chars_${new Date().toISOString().slice(0, 10)}`;
      const raw = window.localStorage.getItem(key);
      if (!raw) return 0;
      const map = JSON.parse(raw) as Record<string, number>;
      return map[bookId] ?? 0;
    } catch {
      return 0;
    }
  }, [bookId, dailyWordsTick]);

  function appendStreamToken(t: string) {
    streamPlainRef.current += t;
    if (chapterIndexRef.current === streamingIndexRef.current) {
      editorRef.current?.appendText(t);
    }
  }

  async function persistChapterStreamPayload(chapterIdx: number, raw: string) {
    if (!bookId) return;
    const { json, text } = streamRawToChapterPayload(raw);
    const cur = qc.getQueryData<Chapter>(["chapter", bookId, chapterIdx]);
    const prev = (cur?.content ?? {}) as Record<string, unknown>;
    const updated = await updateChapter(bookId, chapterIdx, {
      content: {
        ...prev,
        tiptap_json: json,
        text,
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

  function toastAxiosDetail(e: unknown, fallback: string): string {
    const ax = axios.isAxiosError(e) ? e : null;
    const raw = ax?.response?.data;
    if (raw && typeof raw === "object" && "detail" in raw) {
      const d = (raw as { detail: unknown }).detail;
      if (typeof d === "string") return d.length > 280 ? `${d.slice(0, 280)}…` : d;
      if (Array.isArray(d))
        return d
          .map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x)))
          .join("；")
          .slice(0, 280);
    }
    return e instanceof Error ? e.message : fallback;
  }

  async function handleGenerateOutline(payload: {
    topic_override?: string | null;
    target_audience?: string | null;
  }): Promise<boolean> {
    if (!bookId) return false;
    setOutlineBusy(true);
    try {
      await generateOutline(bookId, payload);
      await invalidateAll();
      toast.success("大纲已生成");
      return true;
    } catch (e) {
      console.warn("generateOutline failed", axios.isAxiosError(e) ? e.response?.status : e, axios.isAxiosError(e) ? e.response?.data : e);
      toast.error(toastAxiosDetail(e, "大纲生成失败"));
      return false;
    } finally {
      setOutlineBusy(false);
      await qc.invalidateQueries({ queryKey: ["book", bookId] });
      await qc.invalidateQueries({ queryKey: ["outline", bookId] });
    }
  }

  async function handleSaveOutlineDrawer() {
    if (!bookId || !outline) return;
    const toastId = toast.loading("正在保存大纲…");
    try {
      const chapters: OutlineChapterPatch[] = outline.chapters.map((c) => ({
        index: c.index,
        title: c.title,
        summary: c.summary,
        key_points: c.key_points,
        estimated_words: c.estimated_words,
        sections: c.sections.map((s) => ({ title: s.title, summary: s.summary })),
      }));
      await putOutline(bookId, { chapters });
      await invalidateAll();
      toast.success("大纲已保存", { id: toastId });
    } catch (e) {
      toast.error(toastAxiosDetail(e, "保存失败"), { id: toastId });
    }
  }

  async function startAutoGenerate(chaptersToGenerate: OutlineChapter[]) {
    if (autoGenerating) return;
    setAutoGenPaused(false);
    setAutoGenerating(true);
    autoGenAbortRef.current = false;

    const pending = chaptersToGenerate.filter(
      (c) =>
        c.status === "pending" &&
        !chapterHasBody(qc.getQueryData<Chapter>(["chapter", bookId!, c.index])),
    );
    const total = pending.length;
    let cur = 0;

    for (const ch of pending) {
      if (autoGenAbortRef.current) break;
      cur += 1;
      setAutoGenSlot({ current: cur, total });
      setStreamingIndex(ch.index);
      setSelection({ type: "chapter", index: ch.index });

      await new Promise<void>((resolve) => {
        streamPlainRef.current = "";
        requestAnimationFrame(() => {
          editorRef.current?.clear();
          startStream(bookId!, ch.index, {
            onToken: appendStreamToken,
            onDone: async () => {
              const raw = streamPlainRef.current;
              streamPlainRef.current = "";
              setStreamingIndex(null);
              if (chapterIndexRef.current === ch.index) {
                editorRef.current?.applyPlainMarkdown(raw);
              }
              await persistChapterStreamPayload(ch.index, raw);
              await invalidateAll(ch.index);
              resolve();
            },
            onError: (e) => {
              setStreamingIndex(null);
              toast.error(`第 ${ch.index} 章生成失败，已跳过：${e.message}`);
              resolve();
            },
            onAbort: () => {
              setStreamingIndex(null);
              resolve();
            },
          });
        });
      });

      if (autoGenAbortRef.current) break;

      await new Promise((r) => setTimeout(r, 500));
    }

    const wasAborted = autoGenAbortRef.current;
    autoGenAbortRef.current = false;
    setAutoGenerating(false);
    if (wasAborted) {
      setAutoGenPaused(true);
    } else {
      setAutoGenPaused(false);
      setAutoGenSlot(null);
    }
  }

  async function resumeAutoGenerate() {
    if (!bookId || autoGenerating) return;
    const nextOutline = await getOutline(bookId);
    setAutoGenPaused(false);
    autoGenAbortRef.current = false;
    await startAutoGenerate(nextOutline.chapters);
  }

  async function handleStartWriting(mode: ChapterGenMode = "auto") {
    if (!bookId) return;
    setChapterGenMode(bookId, mode);
    await putOutline(bookId, { chapters: [], confirm_start_writing: true });
    await invalidateAll();
    const nextOutline = await getOutline(bookId);
    const first = nextOutline.chapters[0];
    if (first) setSelection({ type: "chapter", index: first.index });
    if (mode === "auto") {
      toast.success("已进入写作阶段，开始自动生成…");
      setTimeout(() => {
        void startAutoGenerate(nextOutline.chapters);
      }, 800);
    } else {
      toast.success("已进入写作阶段（逐章手动生成）");
    }
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
      if (prev.type === "chapter" && prev.index === idx) {
        const rest = chapters.filter((c) => c.index !== idx);
        const next = rest.sort((a, b) => a.index - b.index)[0];
        return next ? { type: "chapter", index: next.index } : { type: "chapter", index: 1 };
      }
      return prev;
    });
    toast.success("已删除");
  }

  async function handleStreamChapter(idx: number, mode: "generate" | "regenerate") {
    if (!bookId) return;
    const ok =
      mode === "regenerate"
        ? window.confirm("将调用 AI 重新生成该章正文，确定？")
        : window.confirm("调用 AI 生成本章正文？");
    if (!ok) return;
    setStreamingIndex(idx);
    requestAnimationFrame(() => {
      streamPlainRef.current = "";
      editorRef.current?.clear();
      startStream(bookId, idx, {
        onToken: appendStreamToken,
        onDone: async () => {
          const raw = streamPlainRef.current;
          streamPlainRef.current = "";
          setStreamingIndex(null);
          if (chapterIndexRef.current === idx) {
            editorRef.current?.applyPlainMarkdown(raw);
          }
          await persistChapterStreamPayload(idx, raw);
          await invalidateAll(idx);
          toast.success(mode === "regenerate" ? "本章已重新生成" : "本章生成完成");
        },
        onError: (e) => {
          setStreamingIndex(null);
          toast.error(e.message);
        },
        onAbort: () => {
          setStreamingIndex(null);
          streamPlainRef.current = "";
        },
      });
    });
  }

  async function handleAddChapterSubmit(values: AddChapterFormValues) {
    if (!bookId) return;
    setAddOpen(false);
    try {
      const ch = await createChapter(bookId, {
        title: values.title || "新章节",
        summary: values.summary.trim() ? values.summary.trim() : null,
        insert_at: null,
      });
      if (values.keyPoints.length > 0) {
        await putOutline(bookId, {
          chapters: [{ index: ch.index, key_points: values.keyPoints }],
        });
      }
      await invalidateAll();
      setSelection({ type: "chapter", index: ch.index });
      if ((phase === "WRITING" || phase === "COMPLETED") && values.mode === "ai") {
        void handleStreamChapter(ch.index, "generate");
      }
    } catch {
      toast.error("创建章节失败");
      await qc.invalidateQueries({ queryKey: ["book", bookId] });
      await qc.invalidateQueries({ queryKey: ["outline", bookId] });
    }
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
    typeof document !== "undefined" && panelCollapsed && (phase === "WRITING" || phase === "COMPLETED")
      ? createPortal(
          <AuxPanelFab
            onOpen={() => {
              setPanelCollapsed(false);
            }}
          />,
          document.body,
        )
      : null;

  if (phase === "SETUP") {
    return (
      <div className="planning-setup-shell flex w-full flex-col">
        <PlanningWizard
          book={book}
          bookId={bookId}
          outline={outline}
          outlineGeneratingUi={outlineGeneratingUi}
          onPatchBook={(b) => qc.setQueryData(["book", bookId], b)}
          onGenerateOutline={handleGenerateOutline}
          onStartWriting={(mode) => handleStartWriting(mode)}
          onOutlinePatched={() => void invalidateAll()}
          onReorder={handleReorder}
          onDeleteChapter={(idx) => void handleDeleteChapter(idx)}
          dragDisabled={dragDisabled}
        />
      </div>
    );
  }

  return (
    <>
      {/* WPS 式：顶栏 sticky + 中部双栏 + 整页文档滚动 + 固定字数页脚 */}
      <section className="editor-writing-shell editor-page-document-scroll flex flex-col gap-2 px-4 pt-4 sm:px-5 sm:pt-5">
        <header className="editor-wps-topbar">
          <div className="editor-page-outer editor-page-outer--header overflow-visible">
            <div className="editor-topbar-sticky">
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
                autoGenerating={autoGenerating}
                onPauseGeneration={() => {
                  autoGenAbortRef.current = true;
                }}
              />
            </div>
          </div>
        </header>

        <div className="editor-wps-body editor-workspace-split relative flex items-start gap-2 overflow-visible">
              <div
                className={`editor-outline-rail-wrap relative flex min-h-0 shrink-0 flex-col ${
                  outlineRailExpanded ? "w-[280px]" : "w-1"
                }`}
              >
                {!outlineRailExpanded ? (
                  <div className="editor-outline-rail-collapsed-host relative flex min-h-0 flex-1 flex-col items-center justify-center">
                    <button
                      type="button"
                      className="editor-outline-rail-collapsed"
                      title="展开目录"
                      aria-label="展开目录"
                      onClick={() => {
                        setOutlineRailExpanded(true);
                        setOutlineRailTip(false);
                      }}
                    />
                    {outlineRailTip ? (
                      <span className="pointer-events-none absolute -top-1 left-1/2 z-10 -translate-x-1/2 rounded bg-slate-800 px-2 py-1 text-[10px] text-white shadow-md">
                        点击展开目录
                      </span>
                    ) : null}
                  </div>
                ) : (
                  <aside
                    className="editor-outline-sidebar editor-outline-sidebar--expanded editor-outline-sidebar--workspace-split z-[9] min-h-0 w-[280px] shrink-0"
                    aria-label="目录栏"
                  >
                    <button
                      type="button"
                      className="editor-outline-rail-handle"
                      title="收起目录"
                      aria-label="收起目录"
                      onClick={() => {
                        setOutlineRailExpanded(false);
                        if (!window.localStorage.getItem(`autobooker_outline_tip_${bookId}`)) {
                          window.localStorage.setItem(`autobooker_outline_tip_${bookId}`, "1");
                          setOutlineRailTip(true);
                          window.setTimeout(() => setOutlineRailTip(false), 4500);
                        }
                      }}
                    >
                      ▕
                    </button>
                    <div className="editor-outline-sidebar-body">
                      <OutlineNavBody
                        chapters={chapters}
                        selection={selection}
                        onSelect={setSelection}
                        onReorder={handleReorder}
                        onRename={handleRenameChapter}
                        onRegenerate={(idx) => void handleStreamChapter(idx, "regenerate")}
                        onDelete={handleDeleteChapter}
                        onAddChapter={() => setAddOpen(true)}
                        dragDisabled={dragDisabled}
                        showOutlinePreviewNav={false}
                        writingMode
                        streamingChapterIndex={streamingIndex}
                        onOpenGlobalOutline={() => setOutlineDrawerOpen(true)}
                        chapterGenMode={chapterGenMode}
                        autoGenerating={autoGenerating}
                        autoGenSlot={autoGenSlot}
                        autoGenPaused={autoGenPaused}
                        pendingChapterCount={pendingChapterCount}
                        onPauseGeneration={() => {
                          autoGenAbortRef.current = true;
                        }}
                        onResumeGeneration={() => void resumeAutoGenerate()}
                        onGenerateAllRemaining={() => void resumeAutoGenerate()}
                      />
                    </div>
                  </aside>
                )}
              </div>

              <main className="editor-wps-editor-panel editor-center-natural card flex min-w-0 flex-1 flex-col overflow-visible rounded-2xl border border-slate-200/90 bg-white/85 p-0 shadow-[0_18px_40px_rgba(20,30,50,0.06)] backdrop-blur-md">
                <div
                  ref={editorMainScrollRef}
                  className="editor-main-scroll flex min-w-0 flex-col overflow-visible px-4 pb-4 pt-0 sm:px-5 sm:pb-6"
                >
                  {selection.type === "chapter" && (
                    <>
                      {chapterDetailQuery.isLoading && <p className="text-sm text-slate-500">加载章节正文…</p>}
                      {chapterDetail && !chapterDetailQuery.isLoading && (
                        <>
                          {selectedMeta && chapterIndex != null ? (
                            <>
                              <nav className="editor-chapter-nav-strip text-sm">
                              <div className="flex flex-wrap items-center gap-2">
                                {prevChapterIndex != null ? (
                                  <button
                                    type="button"
                                    className="text-slate-600 hover:text-violet-700"
                                    onClick={() => setSelection({ type: "chapter", index: prevChapterIndex })}
                                  >
                                    ‹ 上一章
                                  </button>
                                ) : (
                                  <span className="invisible select-none sm:inline">‹ 上一章</span>
                                )}
                              </div>
                              <span className="text-center text-slate-600">
                                第 {chapterIndex} 章 / 共 {chapters.length} 章
                              </span>
                              <div className="flex flex-wrap items-center justify-end gap-2">
                                <button
                                  type="button"
                                  className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                                  title={chapterNavPrimary?.label ?? ""}
                                  disabled={chapterNavPrimary?.disabled}
                                  onClick={() => {
                                    if (!chapterNavPrimary || chapterNavPrimary.disabled || chapterIndex == null) return;
                                    if (chapterNavPrimary.label === "↺ 重新生成") {
                                      void handleStreamChapter(chapterIndex, "regenerate");
                                    } else if (chapterNavPrimary.label === "▶ 生成本章") {
                                      void handleStreamChapter(chapterIndex, "generate");
                                    }
                                  }}
                                >
                                  {chapterNavPrimary?.label ?? "—"}
                                </button>
                                {nextChapterIndex != null ? (
                                  <button
                                    type="button"
                                    className="text-slate-600 hover:text-violet-700"
                                    onClick={() => setSelection({ type: "chapter", index: nextChapterIndex })}
                                  >
                                    下一章 ›
                                  </button>
                                ) : (
                                  <span className="invisible select-none sm:inline">下一章 ›</span>
                                )}
                              </div>
                            </nav>
                            {autoGenerating && streamingIndex === chapterIndex && (
                              <p className="mb-3 text-xs text-violet-500">AI 生成中…</p>
                            )}
                            </>
                          ) : null}

                          <div className="flex w-full shrink-0 flex-col">
                            <ChapterTiptapEditor
                              ref={editorRef}
                              key={chapterDetail.id}
                              chapter={chapterDetail}
                              readOnly={streamingIndex === chapterIndex}
                              bookId={bookId}
                              chapterIndex={chapterIndex!}
                              onOpenAssistantPanel={(sel) => {
                                setPanelCollapsed(false);
                                setPanelTab("ai");
                                setAssistantSeed(sel);
                              }}
                              onChange={(p) => {
                                setLiveChapterChars(p.characters);
                                recordChars(p.characters);
                                setDailyWordsTick((x) => x + 1);
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
                                });
                              }}
                            />
                          </div>

                          {selectedMeta && chapterIndex != null ? (
                            <div className="mt-10 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-6 text-sm">
                              {prevChapterIndex != null ? (
                                <button
                                  type="button"
                                  className="text-slate-600 hover:text-violet-700"
                                  onClick={() => setSelection({ type: "chapter", index: prevChapterIndex })}
                                >
                                  ‹ 上一章
                                </button>
                              ) : (
                                <span />
                              )}
                              {nextChapterIndex != null ? (
                                <button
                                  type="button"
                                  className="text-slate-600 hover:text-violet-700"
                                  onClick={() => setSelection({ type: "chapter", index: nextChapterIndex })}
                                >
                                  下一章 ›
                                </button>
                              ) : (
                                <span />
                              )}
                            </div>
                          ) : null}

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
                </div>
              </main>

              {!panelCollapsed ? (
                <div className="editor-side-sticky shrink-0">
                  <RightPanel
                    bookId={bookId}
                    onClose={() => setPanelCollapsed(true)}
                    activeChapter={selectedMeta}
                    autoSaveStatus={saveStatus}
                    savedAt={savedAt}
                    aiModel={book.ai_model}
                    onModelChange={(m) => modelMutation.mutate(m)}
                    activeTab={panelTab}
                    onTabChange={setPanelTab}
                    assistantSeed={assistantSeed}
                    onConsumeAssistantSeed={() => setAssistantSeed("")}
                    onInsertReference={(plain, fn) => {
                      editorRef.current?.insertReferenceQuote(plain, fn);
                      editorRef.current?.focusEditor();
                    }}
                    onOpenOutlineEditor={() => setOutlineDrawerOpen(true)}
                  />
                </div>
              ) : null}
            </div>

        {(phase === "WRITING" || phase === "COMPLETED") && selection.type === "chapter" ? (
          <footer className="editor-global-footer">
            <div className="editor-global-footer-inner">
              <span>
                当前章节字数{" "}
                <strong>{(liveChapterChars ?? selectedMeta?.word_count ?? 0).toLocaleString()}</strong>
              </span>
              <span>
                今日总字数 <strong>{todayWords.toLocaleString()}</strong>
              </span>
            </div>
          </footer>
        ) : null}

        <AddChapterDialog open={addOpen} onClose={() => setAddOpen(false)} onSubmit={handleAddChapterSubmit} />
      </section>

      {outline && (
        <OutlineDrawer open={outlineDrawerOpen} title="全局大纲" onClose={() => setOutlineDrawerOpen(false)}>
          <OutlineReviewPanel
            mode="review"
            book={book}
            bookId={bookId}
            outline={outline}
            outlineGeneratingUi={outlineGeneratingUi}
            onSaveOutline={() => void handleSaveOutlineDrawer()}
            onOutlinePatched={() => void invalidateAll()}
            onDeleteChapter={(idx) => void handleDeleteChapter(idx)}
            onReorder={handleReorder}
            dragDisabled={dragDisabled}
            collapsibleAside
            asideStorageKey={`review_outline_aside_${bookId}`}
            leftAside={
              <>
                <h3 className="font-semibold text-ink">书稿设定摘要</h3>
                <dl className="mt-3 space-y-2 text-slate-600">
                  <div>
                    <dt className="text-xs text-slate-400">目标读者</dt>
                    <dd>{book.target_audience?.trim() || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">学科</dt>
                    <dd>{book.discipline?.trim() || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">目标字数</dt>
                    <dd>{book.target_words?.toLocaleString() ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">主题要点</dt>
                    <dd className="whitespace-pre-wrap text-xs leading-relaxed">
                      {typeof window !== "undefined" ? window.localStorage.getItem(topicKey(bookId))?.trim() || "—" : "—"}
                    </dd>
                  </div>
                </dl>
              </>
            }
          />
        </OutlineDrawer>
      )}

      <BookSettingsModal
        open={bookSettingsModalOpen}
        book={book}
        bookId={bookId}
        onClose={() => setBookSettingsModalOpen(false)}
        onSaved={(b) => qc.setQueryData(["book", bookId], b)}
      />

      {auxPanelTrigger}
    </>
  );
}
