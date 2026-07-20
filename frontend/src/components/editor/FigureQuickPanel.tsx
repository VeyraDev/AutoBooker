import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { ArrowDownUp, Loader2, RefreshCw, Upload, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";

import {
  figureGenerationToast,
  generateFigure,
  listFigures,
  loadFigureImageBlob,
  normalizeChapterFiguresTables,
  patchChapterOverviewCaptions,
  resolveFigureUrl,
  startFigureBatch,
  uploadFigure,
  waitFigureBatch,
  type FigureListItem,
  type FigureOut,
  type FigureTableOverviewItem,
} from "@/api/figures";

type Props = {
  bookId: string;
  chapterIndex: number | null;
  initialOverview?: FigureTableOverviewItem[];
  onFiguresChanged?: () => void;
  onFigureGenerated?: (fig: FigureOut) => void;
  getChapterTiptapJson?: () => Record<string, unknown> | null;
  onApplyChapterContent?: (payload: {
    tiptap_json: Record<string, unknown>;
    text: string;
    overview?: FigureTableOverviewItem[];
  }) => void;
  figureListSeed?: { chapter_index?: number; figures?: unknown[] };
};

function figureError(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) {
    const detail = e.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message?: string }).message || fallback);
    }
  }
  return e instanceof Error ? e.message : fallback;
}

function overviewKindLabel(kind: string): string {
  return kind === "table" ? "表格" : "插图";
}

function figureStatusLabel(status: FigureListItem["status"]): string {
  return {
    pending: "待生成",
    generated: "已生成",
    uploaded: "已替换",
    approved: "已确认",
  }[status];
}

function FigureThumbnail({ fig }: { fig: FigureListItem }) {
  const [preferSvg, setPreferSvg] = useState(Boolean(fig.svg_url));
  const [blobUrl, setBlobUrl] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setPreferSvg(Boolean(fig.svg_url));
  }, [fig.id, fig.file_url, fig.svg_url]);

  const url = resolveFigureUrl(preferSvg && fig.svg_url ? fig.svg_url : fig.file_url);
  useEffect(() => {
    let cancelled = false;
    let objectUrl = "";
    setBlobUrl("");
    setFailed(false);
    if (!url) return;
    void loadFigureImageBlob(url)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch(() => {
        if (preferSvg && fig.file_url && fig.file_url !== fig.svg_url) {
          setPreferSvg(false);
        } else {
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fig.file_url, fig.svg_url, preferSvg, url]);

  if (!url || !blobUrl) {
    return (
      <div className="flex h-14 w-20 shrink-0 items-center justify-center rounded border border-dashed border-slate-200 bg-slate-50 text-[10px] text-slate-400">
        {failed ? "加载失败" : url ? "加载中" : "待生成"}
      </div>
    );
  }

  return (
    <img
      src={blobUrl}
      alt=""
      className="h-14 w-20 shrink-0 rounded border border-slate-100 bg-white object-contain"
      onError={() => {
        if (preferSvg && fig.file_url) {
          setPreferSvg(false);
        } else {
          setFailed(true);
        }
      }}
    />
  );
}

export default function FigureQuickPanel({
  bookId,
  chapterIndex,
  initialOverview = [],
  figureListSeed,
  onFiguresChanged,
  onFigureGenerated,
  getChapterTiptapJson,
  onApplyChapterContent,
}: Props) {
  const qc = useQueryClient();
  const uploadTargetRef = useRef<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const captionSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const [sortBusy, setSortBusy] = useState(false);
  const [captionBusy, setCaptionBusy] = useState(false);
  const [overview, setOverview] = useState<FigureTableOverviewItem[]>(initialOverview);

  const { data: figures = [], isLoading, refetch } = useQuery({
    queryKey: ["figures", bookId],
    queryFn: () => listFigures(bookId),
    enabled: !!bookId,
  });

  const chapterFigures =
    chapterIndex != null ? figures.filter((f) => f.chapter === chapterIndex) : [];

  useEffect(() => {
    setOverview(initialOverview);
  }, [chapterIndex, initialOverview]);

  async function invalidate() {
    await qc.invalidateQueries({ queryKey: ["figures", bookId] });
    onFiguresChanged?.();
  }

  /** 打开本章速查时，若正文有图但库内无记录，依赖父级 refresh 回填；此处确保列表最新 */
  useEffect(() => {
    if (chapterIndex == null) return;
    void refetch();
  }, [chapterIndex, bookId]);

  function applyFigureToEditor(fig: FigureOut) {
    onFigureGenerated?.(fig);
  }

  async function handleRegenerate(fig: FigureListItem) {
    setBusyId(fig.id);
    const loading = toast.loading("正在生成图表…");
    try {
      const result = await generateFigure(bookId, fig.id);
      applyFigureToEditor(result);
      await invalidate();
      toast.success(figureGenerationToast(result.quality_report).message, { id: loading });
    } catch (e) {
      toast.error(figureError(e, "生成失败"), { id: loading });
    } finally {
      setBusyId(null);
    }
  }

  async function handleUpload(fig: FigureListItem, file: File) {
    setBusyId(fig.id);
    try {
      const result = await uploadFigure(bookId, fig.id, file);
      applyFigureToEditor(result);
      await invalidate();
      toast.success("已上传并覆盖");
    } catch (e) {
      toast.error(figureError(e, "上传失败"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleBatchGenerate() {
    const pending = chapterFigures.filter((f) => f.status === "pending" || !f.file_url);
    if (pending.length === 0) {
      toast("本章暂无待生成图片");
      return;
    }
    setBatchBusy(true);
    const loading = toast.loading("正在生成本章图片…");
    try {
      const run = await startFigureBatch(bookId, chapterIndex ?? undefined);
      if (run.chapter_index == null && chapterIndex != null && ["pending", "running"].includes(run.status)) {
        toast("全书图片任务正在处理，本章图片已包含在该任务中", { id: loading });
        return;
      }
      if (run.total === 0) {
        toast("本章图片已在其他任务中处理，请稍后刷新", { id: loading });
        return;
      }
      const done = await waitFigureBatch(bookId, run);
      if (["pending", "running"].includes(done.status)) {
        toast("图片仍在后台生成，完成后刷新列表即可查看", { id: loading });
        return;
      }
      const latest = await listFigures(bookId);
      qc.setQueryData(["figures", bookId], latest);
      latest
        .filter((fig) => fig.chapter === chapterIndex && fig.file_url && fig.status !== "pending")
        .forEach((fig) => applyFigureToEditor({
          id: fig.id,
          book_id: bookId,
          chapter_index: fig.chapter,
          figure_number: fig.figure_number,
          figure_type: fig.type,
          status: fig.status,
          caption: fig.caption,
          raw_annotation: fig.raw_annotation,
          file_url: fig.file_url,
          svg_url: fig.svg_url,
          position_hint: fig.position_hint,
          sort_order: null,
          quality_report: fig.quality_report,
        }));
      onFiguresChanged?.();
      if (done.failed) {
        toast(`本章图片已生成 ${done.completed}/${done.total} 张`, { id: loading, icon: "⚠️" });
      } else {
        toast.success(`本章图片已生成 ${done.completed}/${done.total} 张`, { id: loading });
      }
    } catch {
      toast.error("生成本章图片失败，请重试", { id: loading });
    } finally {
      setBatchBusy(false);
    }
  }

  async function handleNormalizeSort() {
    if (chapterIndex == null) return;
    const json = getChapterTiptapJson?.();
    if (!json) {
      toast.error("无法读取当前章节内容，请稍后再试");
      return;
    }
    setSortBusy(true);
    const loading = toast.loading("正在整理本章图表与表格…");
    try {
      const res = await normalizeChapterFiguresTables(bookId, chapterIndex, json);
      setOverview(res.overview);
      onApplyChapterContent?.({
        tiptap_json: res.tiptap_json,
        text: res.text,
        overview: res.overview,
      });
      await invalidate();
      const n = res.overview.length;
      toast.success(n > 0 ? `已整理 ${n} 项图表` : "本章未发现图表或表格", { id: loading });
    } catch (e) {
      toast.error(figureError(e, "整理失败"), { id: loading });
    } finally {
      setSortBusy(false);
    }
  }

  function scheduleCaptionSave(next: FigureTableOverviewItem[]) {
    if (chapterIndex == null) return;
    const json = getChapterTiptapJson?.();
    if (!json) return;
    if (captionSaveTimerRef.current) clearTimeout(captionSaveTimerRef.current);
    captionSaveTimerRef.current = setTimeout(() => {
      captionSaveTimerRef.current = null;
      setCaptionBusy(true);
      void patchChapterOverviewCaptions(bookId, chapterIndex, {
        tiptap_json: json,
        overview: next,
      })
        .then((res) => {
          setOverview(res.overview);
          onApplyChapterContent?.({
            tiptap_json: res.tiptap_json,
            text: res.text,
            overview: res.overview,
          });
        })
        .catch((e) => toast.error(figureError(e, "题注保存失败")))
        .finally(() => setCaptionBusy(false));
    }, 600);
  }

  function handleOverviewTitleChange(index: number, title: string) {
    const next = overview.map((item, i) => (i === index ? { ...item, title } : item));
    setOverview(next);
    scheduleCaptionSave(next);
  }

  return (
    <div className="space-y-4 text-sm">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">图表速览</p>
        {figureListSeed?.figures?.length ? (
          <p className="mt-1 text-xs text-violet-700">
            助手已列出第 {figureListSeed.chapter_index ?? chapterIndex} 章 {figureListSeed.figures.length} 个图表项
          </p>
        ) : null}
        {chapterIndex == null ? (
          <p className="mt-2 text-xs text-slate-500">请选择章节后查看本章插图与图表。</p>
        ) : isLoading ? (
          <p className="mt-2 flex items-center gap-2 text-slate-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            加载中…
          </p>
        ) : chapterFigures.length === 0 ? (
          <p className="mt-2 text-xs text-slate-500">
            本章暂无待生成图片。生成或编辑正文后，系统会识别其中的配图需求。
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {chapterFigures.map((fig) => {
              const label = fig.figure_number ? `图${fig.figure_number}` : fig.caption || fig.type;
              return (
                <li
                  key={fig.id}
                  className="rounded-lg border border-slate-100 bg-white/80 p-2 text-xs text-slate-700"
                >
                  <div className="flex gap-2">
                    <FigureThumbnail fig={fig} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-slate-800">{label}</p>
                      <p className="mt-0.5 text-[10px] text-slate-400">{figureStatusLabel(fig.status)}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 text-violet-700 hover:underline disabled:opacity-50"
                          disabled={busyId === fig.id || batchBusy || sortBusy}
                          onClick={() => void handleRegenerate(fig)}
                        >
                          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                          重新生成
                        </button>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 text-violet-700 hover:underline disabled:opacity-50"
                          disabled={busyId === fig.id || batchBusy || sortBusy}
                          onClick={() => {
                            uploadTargetRef.current = fig.id;
                            fileInputRef.current?.click();
                          }}
                        >
                          <Upload className="h-3.5 w-3.5" aria-hidden />
                          替换图片
                        </button>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {overview.length > 0 ? (
        <div className="rounded-lg border border-violet-100 bg-violet-50/40 p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium text-violet-900">图表总览（本章）</p>
            {captionBusy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-violet-600" aria-hidden />
            ) : null}
          </div>
          <ol className="mt-2 space-y-2 text-[11px] text-slate-700">
            {overview.map((item, index) => (
              <li key={`${item.kind}-${item.seq}`} className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="shrink-0 font-medium text-violet-800">{item.label}</span>
                  <span className="text-slate-500">[{overviewKindLabel(item.kind)}]</span>
                </div>
                <input
                  type="text"
                  className="w-full rounded border border-violet-100 bg-white px-2 py-1 text-[11px] text-slate-800"
                  value={item.title}
                  disabled={sortBusy || captionBusy}
                  onChange={(e) => handleOverviewTitleChange(index, e.target.value)}
                />
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {chapterIndex != null ? (
        <div className="rounded-lg border border-slate-100 bg-slate-50/60 p-3">
          <p className="text-xs font-medium text-slate-600">快捷操作</p>
          <button
            type="button"
            className="btn-secondary mt-2 inline-flex w-full items-center justify-center gap-1.5 text-xs"
            disabled={sortBusy || batchBusy || busyId != null}
            onClick={() => void handleNormalizeSort()}
          >
            {sortBusy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : (
              <ArrowDownUp className="h-3.5 w-3.5" aria-hidden />
            )}
            一键排序
          </button>
          <p className="mt-1.5 text-[10px] leading-relaxed text-slate-500">
            识别本章全部插图与表格，连续编号，补全正文引用与居中题注，并生成总览。
          </p>
          {chapterFigures.length > 0 ? (
            <button
              type="button"
              className="btn-secondary mt-2 inline-flex w-full items-center justify-center gap-1.5 text-xs"
              disabled={batchBusy || busyId != null || sortBusy}
              onClick={() => void handleBatchGenerate()}
            >
              {batchBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <Zap className="h-3.5 w-3.5" aria-hidden />}
              生成本章图片
            </button>
          ) : null}
          <button
            type="button"
            className="mt-2 w-full text-xs text-slate-500 hover:text-slate-700"
            onClick={() => void refetch()}
          >
            刷新列表
          </button>
        </div>
      ) : null}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          const id = uploadTargetRef.current;
          e.target.value = "";
          uploadTargetRef.current = null;
          if (!file || !id) return;
          const fig = chapterFigures.find((f) => f.id === id);
          if (fig) void handleUpload(fig, file);
        }}
      />
    </div>
  );
}
