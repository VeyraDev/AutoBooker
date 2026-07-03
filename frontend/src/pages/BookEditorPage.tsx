import { Loader2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import toast from "react-hot-toast";
import { Link, useNavigate, useParams } from "react-router-dom";

import { patchUserAiModels } from "@/api/auth";
import { EXPORT_EXT, exportBook, getBook, updateBook, duplicateBook, type ExportFormat } from "@/api/books";
import { fetchBookJob } from "@/api/bookJobs";
import {
  cancelChapterGeneration,
  createChapter,
  deleteChapter,
  ensureNarrativeConstitution,
  getChapter,
  reorderChapters,
  updateChapter,
} from "@/api/chapters";
import { generateOutline, getOutline, putOutline } from "@/api/outline";
import { getPreface, openPrefaceGenerateStream, putPreface, type PrefaceData } from "@/api/preface";
import {
  getActiveFigureBatch,
  pauseFigureBatch,
  rebuildChapterBodyFromFigures,
  startFigureBatch,
  waitFigureBatch,
  type FigureBatch,
  type FigureListItem,
  type FigureOut,
  type FigureTableOverviewItem,
} from "@/api/figures";
import AddChapterDialog from "@/components/editor/AddChapterDialog";
import type { AddChapterFormValues } from "@/components/editor/AddChapterDialog";
import BookSettingsModal from "@/components/editor/BookSettingsModal";
import DuplicateBookDialog from "@/components/editor/DuplicateBookDialog";
import ChapterTiptapEditor, { type ChapterEditorHandle } from "@/components/editor/ChapterTiptapEditor";
import EditorTopBar from "@/components/editor/EditorTopBar";
import OutlineDrawer from "@/components/editor/OutlineDrawer";
import OutlineReviewPanel from "@/components/editor/OutlineReviewPanel";
import OutlineNavBody from "@/components/editor/OutlineNavBody";
import type { OutlineSelection } from "@/components/editor/OutlineNavBody";
import PlanningWizard from "@/components/editor/PlanningWizard";
import RightPanel, { AuxPanelFab, type RightPanelTab } from "@/components/editor/RightPanel";
import { getChapterGenMode, setChapterGenMode, type ChapterGenMode } from "@/lib/chapterGenMode";
import { chapterStreamPrimaryIntent } from "@/lib/chapterStreamPrimaryIntent";
import { useAutoSave } from "@/hooks/useAutoSave";
import { isCitationInsufficientError, useChapterStream } from "@/hooks/useChapterStream";
import { useLlmModels } from "@/hooks/useLlmModels";
import { useDailyWordDelta } from "@/hooks/useDailyWordDelta";
import { resolveUserSceneModel } from "@/lib/bookAiModels";
import { phaseOf, type Phase } from "@/lib/bookStatus";
import {
  consumePendingAutoWrite,
  markPendingAutoWrite,
  peekPendingAutoWrite,
} from "@/lib/autoBookWrite";
import { autoBookProgressPath } from "@/lib/bookRoutes";
import { shouldEnterEditor } from "@/lib/autoBookProgress";
import { useAuthStore } from "@/stores/authStore";
import { resolveChapterEditorContent } from "@/lib/resolveChapterEditorContent";
import type { Chapter } from "@/types/chapter";
import { isChapterBodyEffectivelyEmpty } from "@/lib/chapterBodyEmpty";
import type { OutlineChapter, OutlineChapterPatch } from "@/types/outline";

/** 稳定引用：避免 outline 未返回时每次 render 新建 [] 触发下游 effect 抖动 */
const EMPTY_OUTLINE_CHAPTERS: OutlineChapter[] = [];

function pickWritingChapterIndex(
  phase: Phase,
  outlineFetched: boolean,
  chapters: OutlineChapter[],
  selection: OutlineSelection,
): number | null {
  const idx =
    selection.type === "chapter"
      ? selection.index
      : selection.type === "section"
        ? selection.chapterIndex
        : null;
  if (idx == null) return null;
  if (phase !== "WRITING" && phase !== "COMPLETED") return idx;
  if (!outlineFetched) return null;
  if (chapters.length === 0) return null;
  if (chapters.some((c) => c.index === idx)) return idx;
  return chapters[0].index;
}

/** TipTap JSON 内文本节点字符数（用于判断空文档，避免仅有空 doc 误判为「已有正文」导致批量生成跳章） */
function tiptapJsonPlainLen(node: unknown): number {
  if (!node || typeof node !== "object") return 0;
  const o = node as Record<string, unknown>;
  if (o.type === "text" && typeof o.text === "string") return o.text.length;
  if (Array.isArray(o.content)) return o.content.reduce((s: number, x: unknown) => s + tiptapJsonPlainLen(x), 0);
  return 0;
}

function chapterHasBody(c: Chapter | undefined): boolean {
  if (!c?.content || typeof c.content !== "object") return false;
  const co = c.content as Record<string, unknown>;
  const text = typeof co.text === "string" ? co.text.trim() : "";
  if (text.length > 0) return true;
  if (co.tiptap_json && typeof co.tiptap_json === "object") {
    return tiptapJsonPlainLen(co.tiptap_json) > 0;
  }
  return false;
}

function prefaceHasBodyFromData(pf: PrefaceData): boolean {
  if ((pf.word_count ?? 0) > 0) return true;
  if (pf.tiptap_json && tiptapJsonPlainLen(pf.tiptap_json) > 0) return true;
  if (pf.text?.trim()) return true;
  return Boolean(pf.summary?.trim());
}

function prefaceNeedsGeneration(pf: PrefaceData | undefined | null): boolean {
  if (!pf || pf.enabled === false) return false;
  return !prefaceHasBodyFromData(pf);
}

function prefaceToChapter(pf: PrefaceData, bookId: string): Chapter {
  const text = (pf.text || pf.summary || "").trim();
  return {
    id: `preface-${bookId}`,
    index: 0,
    title: "前言",
    summary: pf.brief || null,
    content: {
      tiptap_json: pf.tiptap_json ?? undefined,
      text,
    },
    word_count: pf.word_count ?? 0,
    status: pf.status === "done" ? "done" : pf.status === "generating" ? "generating" : "pending",
  };
}

function streamRawToChapterPayload(raw: string): { json: Record<string, unknown>; text: string } {
  const trimmed = raw.trim();
  if (!trimmed) {
    return { json: { type: "doc", content: [] }, text: "" };
  }
  return {
    json: resolveChapterEditorContent({ text: raw }),
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
  const [streamingPreface, setStreamingPreface] = useState(false);
  const [autoGenerating, setAutoGenerating] = useState(false);
  const [activeFigureBatch, setActiveFigureBatch] = useState<FigureBatch | null>(null);
  const figureBatchGenerating = Boolean(
    activeFigureBatch && ["pending", "running"].includes(activeFigureBatch.status),
  );
  const [outlineDrawerOpen, setOutlineDrawerOpen] = useState(false);
  const [dailyWordsTick, setDailyWordsTick] = useState(0);
  const [panelTab, setPanelTab] = useState<RightPanelTab>("detail");
  const [assistantSeed, setAssistantSeed] = useState("");
  const [quotedFigureId, setQuotedFigureId] = useState<string | null>(null);
  const [quotedFigureAnnotation, setQuotedFigureAnnotation] = useState("");
  const [bookSettingsModalOpen, setBookSettingsModalOpen] = useState(false);
  const [duplicateBookOpen, setDuplicateBookOpen] = useState(false);
  const [duplicateBookBusy, setDuplicateBookBusy] = useState(false);
  const [editorSelectionText, setEditorSelectionText] = useState("");
  const [editorChapterContext, setEditorChapterContext] = useState("");

  const editorRef = useRef<ChapterEditorHandle>(null);
  const editorMainScrollRef = useRef<HTMLDivElement>(null);
  const streamPlainRef = useRef("");
  const streamPreviewRafRef = useRef<number | null>(null);
  const [streamPreviewMd, setStreamPreviewMd] = useState<string | null>(null);
  const autoGenAbortRef = useRef(false);
  const locallyPolledFigureBatchRef = useRef<string | null>(null);
  const forceGenerateCitationsRef = useRef(false);
  const chapterIndexRef = useRef<number | null>(null);
  const streamingIndexRef = useRef<number | null>(null);
  const streamingPrefaceRef = useRef(false);
  const applyingServerContentRef = useRef(false);
  const bodyRebuildAttemptRef = useRef<string | null>(null);
  const prevChapterIndexNavRef = useRef<number | null>(null);
  const { start: startStream } = useChapterStream();
  const { status: saveStatus, savedAt, scheduleSave } = useAutoSave();
  const { recordChars } = useDailyWordDelta(bookId);
  const authUser = useAuthStore((s) => s.user);
  const setAuthUser = useAuthStore((s) => s.setUser);

  const autoWriteStartedRef = useRef(false);
  const [autoWriteRequested, setAutoWriteRequested] = useState(() =>
    Boolean(bookId && peekPendingAutoWrite(bookId)),
  );
  const [autoWriteBooting, setAutoWriteBooting] = useState(() =>
    Boolean(bookId && peekPendingAutoWrite(bookId)),
  );

  const bookQuery = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId!),
    enabled: !!bookId,
  });

  useEffect(() => {
    if (!bookId) return;
    let cancelled = false;
    const refresh = async () => {
      try {
        const active = await getActiveFigureBatch(bookId);
        if (!cancelled) setActiveFigureBatch(active);
      } catch {
        // 顶栏状态恢复失败不阻塞正文编辑；下一轮会自动重试。
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [bookId]);

  const outlineQuery = useQuery({
    queryKey: ["outline", bookId],
    queryFn: () => getOutline(bookId!),
    enabled: !!bookId,
  });

  const llmModelsQuery = useLlmModels();

  const prefaceQuery = useQuery({
    queryKey: ["preface", bookId],
    queryFn: () => getPreface(bookId!),
    enabled: !!bookId,
  });

  const book = bookQuery.data;
  const outline = outlineQuery.data;
  const chapters = useMemo(() => outline?.chapters ?? EMPTY_OUTLINE_CHAPTERS, [outline]);

  /** 一键成书前置未完成时留在进度页 */
  useEffect(() => {
    if (!bookId || !book) return;
    if (book.status === "auto_generating") {
      navigate(autoBookProgressPath(bookId), { replace: true });
      return;
    }
    if (book.status !== "outline_generating") return;
    void fetchBookJob(bookId)
      .then((job) => {
        if (job && (job.status === "pending" || job.status === "running")) {
          navigate(autoBookProgressPath(bookId), { replace: true });
        }
      })
      .catch(() => {
        /* 普通大纲生成不要求存在一键成书任务 */
      });
  }, [bookId, book?.status, navigate]);

  /** 用户离开进度页后再回来时，从持久化 Job 恢复一次自动写作。 */
  useEffect(() => {
    if (!bookId || !book || book.status !== "outline_ready") return;
    if (autoWriteStartedRef.current || peekPendingAutoWrite(bookId)) return;
    void fetchBookJob(bookId)
      .then((job) => {
        if (!job || job.detail?.writing_started || !shouldEnterEditor(job)) return;
        markPendingAutoWrite(bookId);
        setAutoWriteRequested(true);
        setAutoWriteBooting(true);
      })
      .catch(() => {
        /* 没有一键成书任务时保持普通大纲流程 */
      });
  }, [bookId, book?.status]);

  /** 后端同步生成大纲时，刷新页面后 outlineBusy 会丢失；轮询直到状态离开 outline_generating。 */
  useEffect(() => {
    if (!bookId || !book || book.status !== "outline_generating" || outlineBusy) return;
    const tick = () => {
      void qc.invalidateQueries({ queryKey: ["book", bookId] });
      void qc.invalidateQueries({ queryKey: ["outline", bookId] });
    };
    tick();
    const id = window.setInterval(tick, 4000);
    return () => window.clearInterval(id);
  }, [bookId, book?.status, outlineBusy, qc]);

  const phase = book ? phaseOf(book) : "SETUP";

  const chapterIndex = useMemo(
    () =>
      pickWritingChapterIndex(phase, outlineQuery.isFetched, chapters, selection),
    [phase, outlineQuery.isFetched, chapters, selection],
  );

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
    () => (chapterIndex != null ? chapters.find((c) => c.index === chapterIndex) ?? null : null),
    [chapters, chapterIndex],
  );

  const figureTableOverview = useMemo((): FigureTableOverviewItem[] => {
    const co = chapterDetail?.content as Record<string, unknown> | null | undefined;
    const raw = co?.figure_table_overview;
    if (!Array.isArray(raw)) return [];
    return raw.filter(
      (x): x is FigureTableOverviewItem =>
        !!x && typeof x === "object" && typeof (x as FigureTableOverviewItem).label === "string",
    );
  }, [chapterDetail?.id, chapterDetail?.content]);

  /** 绘制前把目录与 selection 对齐，避免侧栏高亮与正文解析 index 短暂不一致 */
  useLayoutEffect(() => {
    if (phase !== "WRITING" && phase !== "COMPLETED") return;
    if (!outlineQuery.isFetched || chapters.length === 0) return;
    const idx =
      selection.type === "chapter"
        ? selection.index
        : selection.type === "section"
          ? selection.chapterIndex
          : null;
    if (idx == null) return;
    if (!chapters.some((c) => c.index === idx)) {
      setSelection({ type: "chapter", index: chapters[0].index });
    }
  }, [phase, outlineQuery.isFetched, chapters, selection]);

  useEffect(() => {
    if (selection.type !== "section" || chapterIndex == null) return;
    if (selection.chapterIndex !== chapterIndex) return;
    if (!chapterDetail || chapterDetailQuery.isPending) return;

    const anchorId = `sec-${selection.chapterIndex}-${selection.sectionIndex}`;
    let cancelled = false;
    const tryScroll = (attempt: number) => {
      if (cancelled) return;
      if (editorRef.current?.scrollToSectionAnchor(anchorId)) return;
      if (attempt < 10) {
        window.setTimeout(() => tryScroll(attempt + 1), 100 + attempt * 80);
      }
    };
    const t = window.setTimeout(() => tryScroll(0), 100);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [selection, chapterIndex, chapterDetail?.id, chapterDetailQuery.isPending]);

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

  useEffect(() => {
    streamingPrefaceRef.current = streamingPreface;
  }, [streamingPreface]);

  const prefaceHasBody = useMemo(() => {
    const pf = prefaceQuery.data;
    if (!pf) return false;
    return prefaceHasBodyFromData(pf);
  }, [prefaceQuery.data]);

  const prefaceChapter = useMemo(() => {
    if (!bookId || !prefaceQuery.data?.enabled) return null;
    return prefaceToChapter(prefaceQuery.data, bookId);
  }, [bookId, prefaceQuery.data]);

  /** 切换章节后整页滚回顶部（整页文档滚动） */
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
    editorMainScrollRef.current?.scrollTo?.({ top: 0, behavior: "auto" });
  }, [chapterDetail?.id]);

  /** 正文被清空但图表库仍有记录时，自动从图表恢复编辑区 */
  useEffect(() => {
    if (!bookId || chapterIndex == null || !chapterDetail) return;
    if (streamingIndex === chapterIndex) return;
    if (bodyRebuildAttemptRef.current === chapterDetail.id) return;

    const co = (chapterDetail.content ?? {}) as Record<string, unknown>;
    if (!isChapterBodyEffectivelyEmpty(co)) return;
    const figuresCache = qc.getQueryData<FigureListItem[]>(["figures", bookId]);
    const hasFigures =
      figureTableOverview.length > 0 ||
      (figuresCache ?? []).some((f) => f.chapter === chapterIndex);
    if (!hasFigures) return;

    bodyRebuildAttemptRef.current = chapterDetail.id;
    void rebuildChapterBodyFromFigures(bookId, chapterIndex)
      .then((res) => {
        applyingServerContentRef.current = true;
        editorRef.current?.applyServerContent({
          tiptap_json: res.tiptap_json,
          text: res.text,
        });
        applyingServerContentRef.current = false;
        const nextContent = {
          ...co,
          tiptap_json: res.tiptap_json,
          text: res.text,
          figure_table_overview: res.overview,
        };
        qc.setQueryData(["chapter", bookId, chapterIndex], {
          ...chapterDetail,
          content: nextContent,
          word_count: res.text.replace(/\s/g, "").length,
        });
        toast.success(`已从 ${res.overview.length} 张图恢复本章正文`);
      })
      .catch(() => {
        bodyRebuildAttemptRef.current = null;
      });
  }, [
    bookId,
    chapterIndex,
    chapterDetail,
    figureTableOverview.length,
    streamingIndex,
    qc,
  ]);

  useEffect(() => {
    bodyRebuildAttemptRef.current = null;
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

  async function handleExport(format: ExportFormat) {
    if (!bookId || !book) return;
    const toastId = toast.loading("正在导出…");
    try {
      const blob = await exportBook(bookId, format);
      const ext = EXPORT_EXT[format];
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

  const chapterBodyByIndex = useMemo(() => {
    const map: Record<number, boolean> = {};
    if (!bookId) return map;
    for (const ch of chapters) {
      map[ch.index] = chapterHasBody(qc.getQueryData<Chapter>(["chapter", bookId, ch.index]));
    }
    return map;
  }, [bookId, chapters, qc, outlineQuery.dataUpdatedAt, chapterDetailQuery.dataUpdatedAt, streamingIndex]);

  const chapterNavPrimary = useMemo(() => {
    if (chapterIndex == null || !selectedMeta) return null;
    const hasBody = chapterHasBody(chapterDetail);
    const intent = chapterStreamPrimaryIntent(selectedMeta, {
      streamingChapterIndex: streamingIndex,
      chapterGenMode,
      autoGenerating,
      hasBody,
    });
    if (intent === "generate") return { intent, label: "▶ 生成本章" as const, disabled: false };
    if (intent === "regenerate") return { intent, label: "↺ 重新生成" as const, disabled: false };
    if (intent === "busy") return { intent, label: "生成中…" as const, disabled: true };
    return { intent, label: "等待中" as const, disabled: true };
  }, [chapterIndex, selectedMeta, streamingIndex, chapterGenMode, autoGenerating, chapterDetail]);

  function handleChapterStreamPrimary(idx: number) {
    const meta = chapters.find((c) => c.index === idx);
    if (!meta) return;
    const hasBody = chapterBodyByIndex[idx] ?? false;
    const intent = chapterStreamPrimaryIntent(meta, {
      streamingChapterIndex: streamingIndex,
      chapterGenMode,
      autoGenerating,
      hasBody,
    });
    if (intent === "generate") void handleStreamChapter(idx, "generate");
    else if (intent === "regenerate") void handleStreamChapter(idx, "regenerate");
  }

  async function runPrefaceGeneration(opts?: { toastOnSuccess?: boolean }): Promise<boolean> {
    if (!bookId) return false;
    if (streamingPreface || streamingIndex != null) return false;

    let pf = prefaceQuery.data;
    if (!pf) {
      try {
        pf = await getPreface(bookId);
      } catch {
        return false;
      }
    }
    if (!prefaceNeedsGeneration(pf)) return false;
    if (autoGenAbortRef.current) return false;

    setStreamingPreface(true);
    streamingPrefaceRef.current = true;
    setSelection({ type: "preface" });
    streamPlainRef.current = "";
    setStreamPreviewMd("");

    try {
      const res = await openPrefaceGenerateStream(bookId);
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let sawDone = false;
      while (true) {
        if (autoGenAbortRef.current) {
          await reader.cancel().catch(() => {});
          return false;
        }
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const payload = JSON.parse(line.slice(5).trim()) as {
            token?: string;
            done?: boolean;
            markdown?: string;
            partial?: boolean;
            error?: string;
          };
          if (payload.token) appendStreamToken(payload.token);
          if (payload.done) {
            sawDone = true;
            const md = typeof payload.markdown === "string" ? payload.markdown : undefined;
            streamPlainRef.current = "";
            await finishPrefaceGeneration(md);
            endStreamPreviewUi();
            if (opts?.toastOnSuccess !== false) {
              toast.success(payload.partial ? "前言已保存（生成未完全结束）" : "前言已生成");
            }
          }
          if (payload.error) throw new Error(payload.error);
        }
      }
      if (!sawDone && streamPlainRef.current.trim()) {
        const partial = streamPlainRef.current;
        streamPlainRef.current = "";
        await finishPrefaceGeneration(partial);
        endStreamPreviewUi();
        toast.success("前言内容已保存");
        return true;
      }
      return sawDone;
    } catch (e) {
      if (!autoGenAbortRef.current) {
        if (streamPlainRef.current.trim()) {
          const partial = streamPlainRef.current;
          streamPlainRef.current = "";
          try {
            await finishPrefaceGeneration(partial);
            endStreamPreviewUi();
            toast.success("前言内容已保存");
            return true;
          } catch {
            /* fall through */
          }
        }
        toast.error(e instanceof Error ? e.message : "前言生成失败");
      }
      return false;
    } finally {
      streamPlainRef.current = "";
      endStreamPreviewUi();
      setStreamingPreface(false);
      streamingPrefaceRef.current = false;
    }
  }

  async function handlePrefaceStreamPrimary() {
    if (!bookId || streamingPreface || streamingIndex != null) return;
    await runPrefaceGeneration({ toastOnSuccess: true });
  }

  async function handlePrefaceDelete() {
    if (!bookId) return;
    try {
      await putPreface(bookId, { enabled: false });
      await qc.invalidateQueries({ queryKey: ["preface", bookId] });
      toast.success("已关闭前言");
      if (selection.type === "preface") {
        const first = chapters[0]?.index ?? 1;
        setSelection({ type: "chapter", index: first });
      }
    } catch (e) {
      toast.error(toastAxiosDetail(e, "操作失败"));
    }
  }

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

  function endStreamPreviewUi() {
    if (streamPreviewRafRef.current != null) {
      cancelAnimationFrame(streamPreviewRafRef.current);
      streamPreviewRafRef.current = null;
    }
    setStreamPreviewMd(null);
  }

  useEffect(() => {
    return () => {
      if (streamPreviewRafRef.current != null) {
        cancelAnimationFrame(streamPreviewRafRef.current);
      }
    };
  }, []);

  function flushStreamPreviewRaf() {
    streamPreviewRafRef.current = null;
    setStreamPreviewMd(streamPlainRef.current);
  }

  function scheduleStreamPreview() {
    if (streamPreviewRafRef.current != null) return;
    streamPreviewRafRef.current = requestAnimationFrame(flushStreamPreviewRaf);
  }

  function appendStreamToken(t: string) {
    streamPlainRef.current += t;
    if (streamingIndexRef.current != null || streamingPrefaceRef.current) {
      scheduleStreamPreview();
    }
  }

  async function finishPrefaceGeneration(markdown?: string) {
    if (!bookId) return;
    const raw = (markdown ?? streamPlainRef.current).trim();
    let updated: PrefaceData;

    if (raw) {
      const { json, text } = streamRawToChapterPayload(raw);
      const wc = text.replace(/\n/g, "").replace(/ /g, "").length;
      try {
        updated = await getPreface(bookId);
      } catch {
        updated = {
          enabled: true,
          target_words: 3000,
          brief: "",
          summary: "",
          status: "empty",
          word_count: 0,
        };
      }
      if (!prefaceHasBodyFromData(updated)) {
        updated = await putPreface(bookId, {
          tiptap_json: json,
          text,
          summary: text.slice(0, 500),
          word_count: wc,
          status: "done",
        });
      } else if (updated.status !== "done") {
        updated = await putPreface(bookId, { status: "done" });
      }
    } else {
      updated = await getPreface(bookId);
    }

    qc.setQueryData(["preface", bookId], updated);
    const co: Record<string, unknown> = {
      tiptap_json: updated.tiptap_json,
      text: updated.text || updated.summary,
    };
    applyingServerContentRef.current = true;
    editorRef.current?.applyServerContent(co);
    applyingServerContentRef.current = false;
  }

  async function finishChapterGeneration(chapterIdx: number) {
    if (!bookId) return;
    const updated = await getChapter(bookId, chapterIdx);
    qc.setQueryData(["chapter", bookId, chapterIdx], updated);
    void qc.invalidateQueries({ queryKey: ["book", bookId] });
    void qc.invalidateQueries({ queryKey: ["outline", bookId] });
    const co = (updated.content ?? {}) as Record<string, unknown>;
    applyingServerContentRef.current = true;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        editorRef.current?.applyServerContent(co);
        applyingServerContentRef.current = false;
      });
    });
  }

  function handleOutlineSelect(s: OutlineSelection) {
    setSelection(s);
  }

  async function invalidateAll(_forChapterIndex?: number | null) {
    await qc.invalidateQueries({ queryKey: ["book", bookId] });
    await qc.invalidateQueries({ queryKey: ["outline", bookId] });
    await qc.invalidateQueries({ queryKey: ["preface", bookId] });
    // 前缀匹配该书下所有章节缓存，避免「开始写作」切换章节后仍用旧 index 只失效一章
    await qc.invalidateQueries({ queryKey: ["chapter", bookId] });
  }

  const titleMutation = useMutation({
    mutationFn: (title: string) => updateBook(bookId!, { title }),
    onSuccess: (b) => {
      qc.setQueryData(["book", bookId], b);
      toast.success("书名已更新");
    },
  });

  const modelMutation = useMutation({
    mutationFn: (writing_ai_model: string) => patchUserAiModels({ writing_ai_model }),
    onSuccess: (u) => setAuthUser(u),
  });

  const assistantModelMutation = useMutation({
    mutationFn: (assistant_ai_model: string) => patchUserAiModels({ assistant_ai_model }),
    onSuccess: (u) => setAuthUser(u),
  });

  const writingModel = resolveUserSceneModel("writing", authUser?.ai_models, llmModelsQuery.data);
  const assistantModel = resolveUserSceneModel("assistant", authUser?.ai_models, llmModelsQuery.data);

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
    topic_brief?: string | null;
  }): Promise<boolean> {
    if (!bookId) return false;
    setOutlineBusy(true);
    try {
      const nextOutline = await generateOutline(bookId, payload);
      qc.setQueryData(["outline", bookId], nextOutline);
      try {
        const freshBook = await getBook(bookId);
        qc.setQueryData(["book", bookId], freshBook);
      } catch {
        /* 回退到 invalidate 后的 refetch */
      }
      await invalidateAll();
      toast.success("大纲已更新");
      return true;
    } catch (e) {
      console.warn("generateOutline failed", axios.isAxiosError(e) ? e.response?.status : e, axios.isAxiosError(e) ? e.response?.data : e);
      toast.error(toastAxiosDetail(e, "大纲生成失败"));
      try {
        const freshBook = await getBook(bookId);
        qc.setQueryData(["book", bookId], freshBook);
      } catch {
        /* ignore */
      }
      return false;
    } finally {
      setOutlineBusy(false);
      await qc.refetchQueries({ queryKey: ["book", bookId] });
      await qc.refetchQueries({ queryKey: ["outline", bookId] });
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
    autoGenAbortRef.current = false;
    forceGenerateCitationsRef.current = false;

    let pf: PrefaceData | null = null;
    if (bookId) {
      try {
        pf = await getPreface(bookId);
      } catch {
        pf = prefaceQuery.data ?? null;
      }
    }
    const needsPreface = prefaceNeedsGeneration(pf);

    const pending = chaptersToGenerate.filter((c) => {
      if (c.status === "done") return false;
      const cached = qc.getQueryData<Chapter>(["chapter", bookId!, c.index]);
      if (chapterHasBody(cached)) return false;
      // 含断流后仍为 generating 但无正文的孤儿章，避免整书批量从第二章开跑
      return c.status === "pending" || c.status === "generating";
    });
    if (pending.length === 0 && !needsPreface) {
      toast("暂无待生成的内容");
      return;
    }

    setAutoGenerating(true);

    if (needsPreface) {
      await runPrefaceGeneration({ toastOnSuccess: false });
      if (autoGenAbortRef.current) {
        setAutoGenerating(false);
        return;
      }
      await new Promise((r) => setTimeout(r, 500));
    }

    if (pending.length === 0) {
      autoGenAbortRef.current = false;
      setAutoGenerating(false);
      toast.success("前言已生成");
      return;
    }

    for (const ch of pending) {
      if (autoGenAbortRef.current) break;
      setStreamingIndex(ch.index);
      setSelection({ type: "chapter", index: ch.index });
      streamPlainRef.current = "";
      setStreamPreviewMd("");

      await new Promise<void>((resolve) => {
        const run = (forceGenerate: boolean) => {
          startStream(
            bookId!,
            ch.index,
            {
              onToken: appendStreamToken,
              onDone: async (payload) => {
                streamPlainRef.current = "";
                await finishChapterGeneration(ch.index);
                endStreamPreviewUi();
                setStreamingIndex(null);
                if (payload?.truncated) {
                  toast("第 ${ch.index} 章可能未写完，建议重新生成", { icon: "⚠️" });
                }
                resolve();
              },
              onError: (e) => {
                if (!forceGenerate && isCitationInsufficientError(e)) {
                  const ok = window.confirm(
                    `${e.message}\n\n是否仍继续生成？（写作中将较少自动引用文献）`,
                  );
                  if (ok) {
                    forceGenerateCitationsRef.current = true;
                    streamPlainRef.current = "";
                    setStreamPreviewMd("");
                    run(true);
                    return;
                  }
                }
                endStreamPreviewUi();
                setStreamingIndex(null);
                toast.error(`第 ${ch.index} 章生成失败，已跳过：${e.message}`);
                void (async () => {
                  try {
                    await cancelChapterGeneration(bookId!, ch.index);
                  } catch {
                    /* ignore */
                  }
                  await invalidateAll();
                })();
                resolve();
              },
              onAbort: () => {
                endStreamPreviewUi();
                setStreamingIndex(null);
                streamPlainRef.current = "";
                void (async () => {
                  try {
                    await cancelChapterGeneration(bookId!, ch.index);
                  } catch {
                    /* ignore */
                  }
                  await invalidateAll();
                })();
                resolve();
              },
            },
            { forceGenerate: forceGenerate || forceGenerateCitationsRef.current },
          );
        };
        run(forceGenerateCitationsRef.current);
      });

      if (autoGenAbortRef.current) break;

      await new Promise((r) => setTimeout(r, 500));
    }

    autoGenAbortRef.current = false;
    setAutoGenerating(false);
  }

  async function resumeAutoGenerate() {
    if (!bookId || autoGenerating) return;
    const nextOutline = await getOutline(bookId);
    autoGenAbortRef.current = false;
    await startAutoGenerate(nextOutline.chapters);
  }

  async function generateBookFigures() {
    if (!bookId) return;
    if (figureBatchGenerating && activeFigureBatch) {
      const runId = activeFigureBatch.id;
      try {
        await pauseFigureBatch(bookId, runId);
        setActiveFigureBatch((current) => current?.id === runId ? null : current);
        if (locallyPolledFigureBatchRef.current !== runId) {
          toast.success("已暂停全书图片生成");
        }
      } catch {
        toast.error("未能暂停全书图片生成，请稍后重试");
      }
      return;
    }
    const loading = toast.loading("正在生成全书图片…");
    let runId: string | null = null;
    try {
      const run = await startFigureBatch(bookId);
      runId = run.id;
      setActiveFigureBatch(run);
      locallyPolledFigureBatchRef.current = run.id;
      const done = await waitFigureBatch(bookId, run);
      await qc.invalidateQueries({ queryKey: ["figures", bookId] });
      if (done.status === "paused") {
        toast.success("已暂停全书图片生成", { id: loading });
      } else if (done.failed) {
        toast(`已生成 ${done.completed}/${done.total} 张，${done.failed} 张可稍后重试`, { id: loading, icon: "⚠️" });
      } else {
        toast.success(done.total ? `全书图片已生成 ${done.completed}/${done.total} 张` : "暂无待生成图片", { id: loading });
      }
    } catch {
      toast.error("未能生成全书图片，请稍后重试", { id: loading });
    } finally {
      if (locallyPolledFigureBatchRef.current === runId) {
        locallyPolledFigureBatchRef.current = null;
      }
      setActiveFigureBatch((current) => current?.id === runId ? null : current);
    }
  }

  async function handleStartWriting(mode: ChapterGenMode = "auto") {
    if (!bookId) return;
    setChapterGenMode(bookId, mode);
    const prepToast = toast.loading("正在生成全书内容，请稍候…");
    try {
      await ensureNarrativeConstitution(bookId);
    } catch {
      toast.dismiss(prepToast);
      toast.error("未能准备写作规则，请稍后重试");
      return;
    }
    toast.dismiss(prepToast);
    try {
      await putOutline(bookId, { chapters: [], confirm_start_writing: true });
    } catch (e) {
      toast.error(toastAxiosDetail(e, "进入写作阶段失败"));
      return;
    }
    // 立即同步书本状态，避免仍停留在 SETUP 导致章节查询未启用 → 主区域空白
    try {
      const freshBook = await getBook(bookId);
      qc.setQueryData(["book", bookId], freshBook);
    } catch {
      /* 若失败仍依赖 invalidate 后的 refetch */
    }
    await invalidateAll();
    const nextOutline = await getOutline(bookId);
    const pf = await getPreface(bookId).catch(() => null);
    if (prefaceNeedsGeneration(pf)) {
      setSelection({ type: "preface" });
    } else {
      const first = nextOutline.chapters[0];
      if (first) setSelection({ type: "chapter", index: first.index });
    }
    if (mode === "auto") {
      toast.success("已进入写作阶段，开始自动生成…");
      setTimeout(() => {
        void (async () => {
          try {
            const freshOutline = await getOutline(bookId);
            await startAutoGenerate(freshOutline.chapters);
          } catch (e) {
            toast.error(e instanceof Error ? e.message : "自动批量生成启动失败");
          }
        })();
      }, 800);
    } else {
      toast.success("已进入写作阶段（逐章手动生成）");
    }
  }

  /** 一键成书：前置完成后进入写作页，复用正常「全部自动生成」流程（含前言 SSE） */
  useEffect(() => {
    if (!bookId) return;
    if (!autoWriteRequested || !peekPendingAutoWrite(bookId)) return;
    if (autoWriteStartedRef.current) return;
    if (!outlineQuery.isFetched || chapters.length === 0) return;
    if (!consumePendingAutoWrite(bookId)) return;
    autoWriteStartedRef.current = true;
    setAutoWriteRequested(false);
    setAutoWriteBooting(true);
    setChapterGenMode(bookId, "auto");
    void handleStartWriting("auto").finally(() => setAutoWriteBooting(false));
  }, [bookId, outlineQuery.isFetched, chapters.length, autoWriteRequested]);

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
        ? window.confirm("将重新生成该章正文，确定吗？")
        : window.confirm("开始生成本章正文？");
    if (!ok) return;
    setSelection({ type: "chapter", index: idx });
    setStreamingIndex(idx);
    streamPlainRef.current = "";
    setStreamPreviewMd("");
    startStream(
      bookId,
      idx,
      {
        onToken: appendStreamToken,
        onDone: async (payload) => {
          streamPlainRef.current = "";
          await finishChapterGeneration(idx);
          endStreamPreviewUi();
          setStreamingIndex(null);
          if (payload?.truncated) {
            toast("本章可能未写完，建议重新生成", { icon: "⚠️" });
          } else {
            toast.success(mode === "regenerate" ? "本章已重新生成" : "本章生成完成");
          }
        },
        onError: (e) => {
          if (isCitationInsufficientError(e)) {
            const ok = window.confirm(
              `${e.message}\n\n是否仍继续生成？（写作中将较少自动引用文献）`,
            );
            if (ok) {
              forceGenerateCitationsRef.current = true;
              streamPlainRef.current = "";
              setStreamPreviewMd("");
              startStream(
                bookId,
                idx,
                {
                  onToken: appendStreamToken,
                  onDone: async (payload) => {
                    streamPlainRef.current = "";
                    await finishChapterGeneration(idx);
                    endStreamPreviewUi();
                    setStreamingIndex(null);
                    if (payload?.truncated) {
                      toast("本章可能未写完，建议重新生成", { icon: "⚠️" });
                    } else {
                      toast.success(mode === "regenerate" ? "本章已重新生成" : "本章生成完成");
                    }
                  },
                  onError: (retryErr) => {
                    endStreamPreviewUi();
                    setStreamingIndex(null);
                    toast.error(retryErr.message);
                    void (async () => {
                      try {
                        await cancelChapterGeneration(bookId, idx);
                      } catch {
                        /* ignore */
                      }
                      await invalidateAll();
                    })();
                  },
                  onAbort: () => {
                    endStreamPreviewUi();
                    setStreamingIndex(null);
                    streamPlainRef.current = "";
                    void (async () => {
                      try {
                        await cancelChapterGeneration(bookId, idx);
                      } catch {
                        /* ignore */
                      }
                      await invalidateAll();
                    })();
                  },
                },
                { forceGenerate: true },
              );
              return;
            }
          }
          endStreamPreviewUi();
          setStreamingIndex(null);
          toast.error(e.message);
          void (async () => {
            try {
              await cancelChapterGeneration(bookId, idx);
            } catch {
              /* ignore */
            }
            await invalidateAll();
          })();
        },
        onAbort: () => {
          endStreamPreviewUi();
          setStreamingIndex(null);
          streamPlainRef.current = "";
          void (async () => {
            try {
              await cancelChapterGeneration(bookId, idx);
            } catch {
              /* ignore */
            }
            await invalidateAll();
          })();
        },
      },
      { forceGenerate: forceGenerateCitationsRef.current },
    );
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
            返回我的书稿
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
    if (autoWriteBooting) {
      return (
        <div className="planning-setup-shell flex w-full flex-col items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
          <p className="mt-4 text-sm text-slate-600">正在进入写作页并启动全书生成…</p>
        </div>
      );
    }
    return (
      <div className="planning-setup-shell flex w-full flex-col">
        <PlanningWizard
          book={book}
          bookId={bookId}
          outline={outline}
          outlineRequestPending={outlineBusy}
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
      {/* WPS 式：顶栏 + 目录 + 正文同色底板无缝拼合；整页文档滚动 + 固定字数页脚 */}
      <section className="editor-writing-shell editor-writing-shell--wps-board editor-page-document-scroll flex w-full min-w-0 flex-col gap-0 overflow-x-hidden">
        <header className="editor-wps-topbar">
          <EditorTopBar
            title={book.title}
            currentWords={currentWords}
            targetWords={targetWords}
            aiModel={writingModel}
            llmCatalog={llmModelsQuery.data}
            llmCatalogLoading={llmModelsQuery.isLoading}
            onTitleSave={(t) => titleMutation.mutate(t)}
            onModelChange={(m) => modelMutation.mutate(m)}
            autoSaveStatus={saveStatus}
            savedAt={savedAt}
            onBack={() => navigate("/app/books")}
            onExport={handleExport}
            autoGenerating={autoGenerating}
            onPauseGeneration={() => {
              autoGenAbortRef.current = true;
              setAutoGenerating(false);
            }}
            onStartBatchGeneration={() => void resumeAutoGenerate()}
            figureBatchGenerating={figureBatchGenerating}
            onGenerateBookFigures={() => void generateBookFigures()}
          />
        </header>

        <div className="editor-wps-body editor-workspace-split relative flex min-w-0 items-start gap-0 overflow-visible">
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
                        onSelect={handleOutlineSelect}
                        onReorder={handleReorder}
                        onRename={handleRenameChapter}
                        onChapterStreamPrimary={handleChapterStreamPrimary}
                        chapterBodyByIndex={chapterBodyByIndex}
                        onDelete={handleDeleteChapter}
                        onAddChapter={() => setAddOpen(true)}
                        dragDisabled={dragDisabled}
                        showOutlinePreviewNav={false}
                        writingMode
                        streamingChapterIndex={streamingIndex}
                        onOpenGlobalOutline={() => setOutlineDrawerOpen(true)}
                        chapterGenMode={chapterGenMode}
                        autoGenerating={autoGenerating}
                        prefaceEnabled={prefaceQuery.data?.enabled !== false}
                        prefaceHasBody={prefaceHasBody}
                        prefaceStatus={prefaceQuery.data?.status ?? "empty"}
                        streamingPreface={streamingPreface}
                        onPrefaceStreamPrimary={() => void handlePrefaceStreamPrimary()}
                        onPrefaceDelete={() => void handlePrefaceDelete()}
                      />
                    </div>
                  </aside>
                )}
              </div>

              <main className="editor-wps-editor-panel editor-center-natural editor-wps-main-surface flex min-w-0 flex-1 flex-col overflow-visible p-0">
                <div
                  ref={editorMainScrollRef}
                  className="editor-main-scroll flex min-w-0 flex-col overflow-visible px-4 pb-6 pt-0 sm:px-6 sm:pb-8"
                >
                  {selection.type === "preface" && bookId && prefaceChapter ? (
                    <>
                      <nav className="editor-chapter-nav-strip text-sm">
                        <span />
                        <span className="text-center text-slate-600">前言</span>
                        <div className="flex flex-wrap items-center justify-end gap-2">
                          <button
                            type="button"
                            className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={streamingPreface || streamingIndex != null}
                            onClick={() => void handlePrefaceStreamPrimary()}
                          >
                            {streamingPreface
                              ? "生成中…"
                              : prefaceHasBody
                                ? "重新生成"
                                : "生成前言"}
                          </button>
                        </div>
                      </nav>
                      {streamingPreface ? (
                        <p className="mb-3 text-xs text-violet-500">AI 生成中，请稍候…</p>
                      ) : null}
                      <ChapterTiptapEditor
                        ref={editorRef}
                        key={prefaceChapter.id}
                        chapter={prefaceChapter}
                        readOnly={streamingPreface}
                        streamingMarkdown={
                          streamingPreface && streamPreviewMd !== null ? streamPreviewMd : null
                        }
                        bookId={bookId}
                        chapterIndex={0}
                        onOpenAssistantPanel={(sel) => {
                          setPanelCollapsed(false);
                          setPanelTab("ai");
                          setAssistantSeed(sel);
                        }}
                        onQuoteFigure={(figureId, annotation) => {
                          setQuotedFigureId(figureId);
                          setQuotedFigureAnnotation(annotation);
                          setPanelCollapsed(false);
                          setPanelTab("ai");
                        }}
                        onSelectionChange={(sel) => {
                          setEditorSelectionText(sel);
                          setEditorChapterContext(
                            editorRef.current?.getChapterContextAroundSelection() ?? "",
                          );
                        }}
                        onChange={(p) => {
                          if (streamingPreface || applyingServerContentRef.current) return;
                          setLiveChapterChars(p.characters);
                          recordChars(p.characters);
                          setDailyWordsTick((x) => x + 1);
                          scheduleSave(async () => {
                            const updated = await putPreface(bookId, {
                              tiptap_json: p.json,
                              text: p.text,
                              summary: p.text.slice(0, 500),
                              word_count: p.characters,
                            });
                            qc.setQueryData(["preface", bookId], updated);
                          });
                        }}
                      />
                    </>
                  ) : null}

                  {selection.type === "chapter" || selection.type === "section" ? (
                    <>
                      {!outlineQuery.isFetched ? (
                        <p className="text-sm text-slate-500">加载目录与章节…</p>
                      ) : chapterIndex == null ? (
                        <p className="text-sm text-slate-500">
                          暂无章节。请使用侧栏「添加章节」，或返回策划页检查大纲。
                        </p>
                      ) : (
                        <>
                      {chapterDetailQuery.isPending && (
                        <p className="text-sm text-slate-500">加载章节正文…</p>
                      )}
                      {chapterDetailQuery.isError ? (
                        <div className="rounded-lg border border-red-100 bg-red-50/80 px-3 py-4 text-sm text-red-800">
                          <p className="font-medium">章节加载失败</p>
                          <p className="mt-1 text-xs text-red-700/90">
                            请检查是否已登录或网络正常；若接口返回 401，请先重新登录。
                          </p>
                          <button
                            type="button"
                            className="mt-3 text-sm font-medium text-violet-700 underline hover:text-violet-900"
                            onClick={() => void chapterDetailQuery.refetch()}
                          >
                            重新加载
                          </button>
                        </div>
                      ) : null}
                      {chapterDetail ? (
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
                                    if (chapterNavPrimary.intent === "regenerate") {
                                      void handleStreamChapter(chapterIndex, "regenerate");
                                    } else if (chapterNavPrimary.intent === "generate") {
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
                            {streamingIndex === chapterIndex && (
                              <p className="mb-3 text-xs text-violet-500">AI 生成中，请稍候…</p>
                            )}
                            </>
                          ) : null}

                          <ChapterTiptapEditor
                            ref={editorRef}
                            key={chapterDetail.id}
                            chapter={chapterDetail}
                            readOnly={streamingIndex === chapterIndex}
                            streamingMarkdown={
                              streamingIndex != null &&
                              chapterIndex != null &&
                              streamingIndex === chapterIndex &&
                              streamPreviewMd !== null
                                ? streamPreviewMd
                                : null
                            }
                            bookId={bookId}
                            chapterIndex={chapterIndex!}
                            onOpenAssistantPanel={(sel) => {
                              setPanelCollapsed(false);
                              setPanelTab("ai");
                              setAssistantSeed(sel);
                            }}
                            onQuoteFigure={(figureId, annotation) => {
                              setQuotedFigureId(figureId);
                              setQuotedFigureAnnotation(annotation);
                              setPanelCollapsed(false);
                              setPanelTab("ai");
                            }}
                            onSelectionChange={(sel) => {
                              setEditorSelectionText(sel);
                              setEditorChapterContext(
                                editorRef.current?.getChapterContextAroundSelection() ?? "",
                              );
                            }}
                            onChange={(p) => {
                              if (
                                streamingIndex === chapterIndex ||
                                applyingServerContentRef.current
                              )
                                return;
                              const prevCo = (chapterDetail.content ?? {}) as Record<string, unknown>;
                              if (
                                chapterHasBody(chapterDetail) &&
                                isChapterBodyEffectivelyEmpty({
                                  text: p.text,
                                  tiptap_json: p.json,
                                }) &&
                                !isChapterBodyEffectivelyEmpty(prevCo)
                              ) {
                                return;
                              }
                              setLiveChapterChars(p.characters);
                              recordChars(p.characters);
                              setDailyWordsTick((x) => x + 1);
                              scheduleSave(async () => {
                                const prev = (chapterDetail.content ?? {}) as Record<string, unknown>;
                                const updated = await updateChapter(bookId!, chapterIndex!, {
                                  content: {
                                    ...prev,
                                    tiptap_json: p.json,
                                    text: p.text,
                                  },
                                });
                                qc.setQueryData(["chapter", bookId, chapterIndex], updated);
                                void qc.invalidateQueries({ queryKey: ["book", bookId] });
                                void qc.invalidateQueries({ queryKey: ["outline", bookId] });
                              });
                            }}
                          />

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
                      ) : !chapterDetailQuery.isPending && !chapterDetailQuery.isError ? (
                        <p className="text-sm text-slate-500">
                          暂无该章节数据。若大纲为空，请返回上一步检查大纲。
                        </p>
                      ) : null}
                        </>
                      )}
                    </>
                  ) : null}
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
                    aiModel={assistantModel}
                    llmCatalog={llmModelsQuery.data}
                    llmCatalogLoading={llmModelsQuery.isLoading}
                    onModelChange={(m) => assistantModelMutation.mutate(m)}
                    activeTab={panelTab}
                    onTabChange={setPanelTab}
                    assistantSeed={assistantSeed}
                    onConsumeAssistantSeed={() => setAssistantSeed("")}
                    citationStyle={book.citation_style}
                    onInsertReference={(plain, fn) => {
                      editorRef.current?.insertReferenceQuote(plain, fn);
                      editorRef.current?.focusEditor();
                    }}
                    onPreviewCitationInsert={({ sentence, node }) => {
                      editorRef.current?.insertCitationContent(sentence, node);
                      editorRef.current?.focusEditor();
                    }}
                    onJumpToCitation={(targetChapterIndex, nodeId) => {
                      setSelection({ type: "chapter", index: targetChapterIndex });
                      let attempts = 0;
                      const focusNode = () => {
                        const node = document.querySelector(
                          `[data-citation-node-id="${CSS.escape(nodeId)}"]`,
                        );
                        if (node) {
                          node.scrollIntoView({ behavior: "smooth", block: "center" });
                          return;
                        }
                        attempts += 1;
                        if (attempts < 8) window.setTimeout(focusNode, 250);
                      };
                      window.setTimeout(focusNode, 100);
                    }}
                    chapterIndex={chapterIndex}
                    editorSelectionText={editorSelectionText}
                    chapterContext={editorChapterContext}
                    onApplyReviewFix={(quote, suggestion) => {
                      const ok = editorRef.current?.replaceQuoteWithSuggestion(quote, suggestion);
                      if (ok) {
                        toast.success("已应用修改建议");
                        editorRef.current?.focusEditor();
                      } else {
                        toast.error("未在正文中定位到对应片段，请手动修改");
                      }
                    }}
                    onAiPreviewReady={(payload) => {
                      const ok = editorRef.current?.showAiPreview(payload);
                      if (!ok) {
                        toast.error("未在正文中定位到对应片段，请核对原文或手动选中后重试");
                        return false;
                      }
                      editorRef.current?.focusEditor();
                      return true;
                    }}
                    onChapterMarkdownReplace={(markdown) => {
                      editorRef.current?.applyServerContent({ text: markdown });
                      editorRef.current?.focusEditor();
                    }}
                    quotedFigureId={quotedFigureId}
                    quotedFigureAnnotation={quotedFigureAnnotation}
                    onClearFigureQuote={() => {
                      setQuotedFigureId(null);
                      setQuotedFigureAnnotation("");
                    }}
                    onFigureReady={(fig) => {
                      editorRef.current?.applyFigureResult(fig, {
                        replaceOnly: fig.replace_only,
                        targetFigureId: fig.target_figure_id,
                      });
                      editorRef.current?.focusEditor();
                    }}
                    onOpenOutlineEditor={() => setOutlineDrawerOpen(true)}
                    onFiguresChanged={() => {
                      void qc.invalidateQueries({ queryKey: ["figures", bookId] });
                    }}
                    onFigureGenerated={(fig: FigureOut) => {
                      editorRef.current?.applyFigureResult(
                        {
                          figure_id: fig.id,
                          file_url: fig.file_url,
                          svg_url: fig.svg_url,
                          figure_number: fig.figure_number,
                          status: fig.status,
                          caption: fig.caption,
                          figure_type: fig.figure_type,
                          updated_at: fig.updated_at,
                        },
                        { targetFigureId: fig.id },
                      );
                    }}
                    figureTableOverview={figureTableOverview}
                    getChapterTiptapJson={() =>
                      editorRef.current?.getSerialized()?.json ?? null
                    }
                    onApplyChapterContent={(payload) => {
                      applyingServerContentRef.current = true;
                      editorRef.current?.applyServerContent({
                        tiptap_json: payload.tiptap_json,
                        text: payload.text,
                      });
                      applyingServerContentRef.current = false;
                      if (chapterIndex != null && bookId && chapterDetail) {
                        scheduleSave(async () => {
                          const prev = (chapterDetail.content ?? {}) as Record<string, unknown>;
                          const updated = await updateChapter(bookId, chapterIndex, {
                            content: {
                              ...prev,
                              tiptap_json: payload.tiptap_json,
                              text: payload.text,
                              ...(payload.overview ? { figure_table_overview: payload.overview } : {}),
                            },
                          });
                          qc.setQueryData(["chapter", bookId, chapterIndex], updated);
                          void qc.invalidateQueries({ queryKey: ["book", bookId] });
                          void qc.invalidateQueries({ queryKey: ["outline", bookId] });
                        });
                      }
                      editorRef.current?.focusEditor();
                    }}
                  />
                </div>
              ) : null}
            </div>

        {(phase === "WRITING" || phase === "COMPLETED") &&
        (selection.type === "chapter" ||
          selection.type === "section" ||
          selection.type === "preface") ? (
          <footer className="editor-global-footer">
            <div className="editor-global-footer-inner">
              <span>
                {selection.type === "preface" ? "前言字数" : "当前章节字数"}{" "}
                <strong>
                  {(selection.type === "preface"
                    ? prefaceQuery.data?.word_count ?? liveChapterChars
                    : liveChapterChars ?? selectedMeta?.word_count ?? 0
                  )?.toLocaleString?.() ?? 0}
                </strong>
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
                <div className="mb-2 flex items-center justify-between gap-2">
                  <button
                    type="button"
                    className="inline-flex h-8 items-center rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    onClick={() => setDuplicateBookOpen(true)}
                  >
                    基于本书新建
                  </button>
                </div>
                <h3 className="font-semibold text-ink">书稿设定摘要</h3>
                <dl className="mt-3 space-y-2 text-slate-600">
                  <div>
                    <dt className="text-xs text-slate-400">目标读者</dt>
                    <dd>{book.target_audience?.trim() || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">学科</dt>
                    <dd>
                      {book.disciplines?.length
                        ? book.disciplines.join("、")
                        : book.discipline?.trim() || "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">目标字数</dt>
                    <dd>{book.target_words?.toLocaleString() ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">主题要点</dt>
                    <dd className="whitespace-pre-wrap text-xs leading-relaxed">
                      {book.topic_brief?.trim() || "—"}
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

      {book ? (
        <DuplicateBookDialog
          open={duplicateBookOpen}
          bookTitle={book.title}
          hasOutline={chapters.length > 0}
          chapterCount={chapters.length}
          busy={duplicateBookBusy}
          onClose={() => !duplicateBookBusy && setDuplicateBookOpen(false)}
          onConfirm={(copyOutline) => {
            void (async () => {
              setDuplicateBookBusy(true);
              try {
                const { book: newBook, message } = await duplicateBook(bookId, { copy_outline: copyOutline });
                toast.success(message);
                setDuplicateBookOpen(false);
                navigate(`/app/books/${newBook.id}`);
              } catch {
                toast.error("创建副本失败");
              } finally {
                setDuplicateBookBusy(false);
              }
            })();
          }}
        />
      ) : null}

      {auxPanelTrigger}
    </>
  );
}
