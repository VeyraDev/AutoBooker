import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { ChevronDown, ChevronRight, Trash2 } from "lucide-react";
import { useCallback, useRef, useState, type DragEvent } from "react";
import toast from "react-hot-toast";

import { deleteCitation, listCitations } from "@/api/citations";
import type { SourceItem } from "@/features/assistant/api/assistantApi";
import {
  confirmSourceSegment,
  deleteSource,
  pasteSource,
  readSource,
  uploadSource,
} from "@/features/assistant/api/assistantApi";

const STATUS_LABEL: Record<string, string> = {
  reading: "正在读取",
  read: "已读取",
  needs_confirm: "需要确认",
  failed: "读取失败",
  indexed: "全文已索引",
};

const SEGMENT_TYPE_LABEL: Record<string, string> = {
  outline: "大纲/目录",
  requirement: "写作要求",
  manuscript: "正文/初稿",
  preface: "前言",
  chapter_draft: "章节草稿",
  bibliography: "参考文献",
  style_sample: "文风样章",
  case_material: "案例素材",
  table_material: "表格素材",
  figure_material: "图表素材",
};

const STAGE_LABEL: Record<string, string> = {
  outline: "大纲",
  narrative: "叙事宪法",
  chapter: "章节写作",
  review: "审校",
};

function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data;
    if (detail && typeof detail === "object" && "detail" in detail) {
      const raw = (detail as { detail: unknown }).detail;
      if (typeof raw === "string") return raw;
      if (Array.isArray(raw)) {
        return raw
          .map((item) => (typeof item === "object" ? JSON.stringify(item) : String(item)))
          .join("；");
      }
    }
    if (error.code === "ECONNABORTED") return "上传超时，请检查网络或换较小文件重试";
  }
  return error instanceof Error ? error.message : fallback;
}

type Props = {
  bookId: string;
  sources: SourceItem[];
  loading?: boolean;
  error?: unknown;
  onRefresh: () => void | Promise<void>;
  onSourceUploaded?: (item: SourceItem) => void;
  onSourceRemoved?: (sourceId: string) => void;
};

function confidenceLabel(value: number) {
  const pct = Math.round(value * 100);
  if (value < 0.7) return `${pct}% · 需确认`;
  return `${pct}%`;
}

function statusBadgeClass(status: string) {
  if (status === "failed") return "text-red-600";
  if (status === "needs_confirm") return "text-amber-600";
  if (status === "reading") return "text-indigo-600";
  if (status === "indexed") return "text-emerald-600";
  return "text-slate-500";
}

export default function SourceLibraryPanel({
  bookId,
  sources,
  loading,
  error,
  onRefresh,
  onSourceUploaded,
  onSourceRemoved,
}: Props) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const dragDepthRef = useRef(0);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [expandedSegments, setExpandedSegments] = useState<Record<string, boolean>>({});
  const uploadingRef = useRef(false);

  const citationsQuery = useQuery({
    queryKey: ["citations", bookId],
    queryFn: () => listCitations(bookId),
    enabled: Boolean(bookId),
  });
  const citations = citationsQuery.data ?? [];

  const toggleSource = useCallback((sourceId: string) => {
    setExpandedSources((prev) => ({ ...prev, [sourceId]: !prev[sourceId] }));
  }, []);

  const toggleSegments = useCallback((sourceId: string) => {
    setExpandedSegments((prev) => ({ ...prev, [sourceId]: !prev[sourceId] }));
  }, []);

  const uploadFiles = useCallback(
    async (files: FileList | File[] | null | undefined) => {
      const list = files ? Array.from(files).filter((f) => f.size > 0) : [];
      if (!list.length || uploadingRef.current) return;
      uploadingRef.current = true;
      setBusy(true);
      const toastId = toast.loading(list.length > 1 ? `正在上传 ${list.length} 个文件…` : "正在上传…");
      const uploaded: SourceItem[] = [];
      try {
        for (const file of list) {
          const item = await uploadSource(bookId, file);
          uploaded.push(item);
          onSourceUploaded?.(item);
        }
        await onRefresh();
        toast.success(
          list.length > 1 ? `已上传 ${list.length} 个文件` : `已上传「${list[0]?.name ?? uploaded[0]?.title ?? "文件"}」`,
          { id: toastId },
        );
      } catch (err) {
        const fallback =
          uploaded.length > 0
            ? `部分文件上传失败（已成功 ${uploaded.length} 个）`
            : "上传失败，请重试";
        toast.error(apiErrorMessage(err, fallback), { id: toastId });
        if (uploaded.length > 0) {
          await onRefresh();
        }
      } finally {
        uploadingRef.current = false;
        setBusy(false);
        if (fileRef.current) fileRef.current.value = "";
      }
    },
    [bookId, onRefresh, onSourceUploaded],
  );

  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepthRef.current += 1;
    if (e.dataTransfer.types.includes("Files")) {
      setDragOver(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setDragOver(false);
    }
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.types.includes("Files")) {
      e.dataTransfer.dropEffect = "copy";
    }
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragDepthRef.current = 0;
      setDragOver(false);
      void uploadFiles(e.dataTransfer.files);
    },
    [uploadFiles],
  );

  async function handlePaste() {
    if (!pasteText.trim()) return;
    setBusy(true);
    const toastId = toast.loading("正在添加…");
    try {
      const item = await pasteSource(bookId, pasteText.trim());
      onSourceUploaded?.(item);
      setPasteText("");
      setPasteOpen(false);
      await onRefresh();
      toast.success("已添加文本资料", { id: toastId });
    } catch (err) {
      toast.error(apiErrorMessage(err, "添加失败"), { id: toastId });
    } finally {
      setBusy(false);
    }
  }

  async function handleRead(sourceId: string) {
    setBusy(true);
    const toastId = toast.loading("正在读取…");
    try {
      await readSource(bookId, sourceId);
      await onRefresh();
      toast.success("读取完成", { id: toastId });
    } catch (err) {
      toast.error(apiErrorMessage(err, "读取失败"), { id: toastId });
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(source: SourceItem) {
    if (!window.confirm(`确定删除「${source.title}」？删除后助手将不再引用该资料。`)) return;
    setBusy(true);
    const toastId = toast.loading("正在删除…");
    try {
      await deleteSource(bookId, source.id);
      onSourceRemoved?.(source.id);
      setExpandedSources((prev) => {
        const next = { ...prev };
        delete next[source.id];
        return next;
      });
      setExpandedSegments((prev) => {
        const next = { ...prev };
        delete next[source.id];
        return next;
      });
      await onRefresh();
      toast.success("已删除", { id: toastId });
    } catch (err) {
      toast.error(apiErrorMessage(err, "删除失败"), { id: toastId });
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirmSegment(segmentId: string, confirmed: boolean) {
    setBusy(true);
    try {
      await confirmSourceSegment(bookId, segmentId, confirmed);
      await onRefresh();
      toast.success(confirmed ? "已确认用途" : "已排除该片段");
    } catch (err) {
      toast.error(apiErrorMessage(err, "操作失败"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteCitation(id: string, title: string) {
    if (!window.confirm(`确定删除引用「${title}」？`)) return;
    setBusy(true);
    try {
      await deleteCitation(bookId, id);
      await qc.invalidateQueries({ queryKey: ["citations", bookId] });
      toast.success("已删除引用");
    } catch (err) {
      toast.error(apiErrorMessage(err, "删除引用失败"));
    } finally {
      setBusy(false);
    }
  }

  const emptyAll = !loading && !sources.length && !citationsQuery.isLoading && !citations.length;

  return (
    <div className="flex h-full flex-col border-l border-slate-200">
      <div className="border-b border-slate-200 px-3 py-2">
        <h3 className="text-sm font-semibold text-slate-800">资料库</h3>
        <div
          className={`mt-2 rounded-lg border-2 border-dashed px-3 py-4 text-center transition-colors ${
            dragOver
              ? "border-indigo-400 bg-indigo-50"
              : "border-slate-200 bg-slate-50/80 hover:border-slate-300"
          } ${busy ? "pointer-events-none opacity-60" : ""}`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <p className="text-xs text-slate-600">
            {dragOver ? "松开即可上传" : "拖拽文件到此处"}
          </p>
          <p className="mt-1 text-[10px] text-slate-400">支持 PDF、DOCX、TXT 等</p>
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            <input
              ref={fileRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => void uploadFiles(e.target.files)}
            />
            <button
              type="button"
              className="rounded border border-slate-300 bg-white px-2 py-1 text-xs disabled:opacity-50"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
            >
              {busy ? "上传中…" : "选择文件"}
            </button>
            <button type="button" className="rounded border border-slate-300 bg-white px-2 py-1 text-xs" onClick={() => setPasteOpen((v) => !v)}>
              粘贴文本
            </button>
          </div>
        </div>
        {pasteOpen ? (
          <div className="mt-2 space-y-2">
            <textarea
              className="w-full rounded border p-2 text-xs"
              rows={3}
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
            />
            <button type="button" className="rounded bg-slate-800 px-2 py-1 text-xs text-white" onClick={() => void handlePaste()}>
              添加
            </button>
          </div>
        ) : null}
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-3">
        {error ? <div className="text-xs text-red-600">资料加载失败</div> : null}
        {emptyAll ? (
          <div className="text-xs text-slate-400">暂无文件或引用。上传文件，或在对话中勾选文献加入。</div>
        ) : null}

        <section>
          <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            文件（{sources.length}）
          </h4>
          {loading ? <div className="text-xs text-slate-500">加载文件…</div> : null}
          {!loading && !sources.length ? (
            <p className="text-[11px] text-slate-400">暂无上传文件</p>
          ) : null}
          <ul className="space-y-2">
          {sources.map((s) => {
            const sourceOpen = Boolean(expandedSources[s.id]);
            const segmentsOpen = Boolean(expandedSegments[s.id]);
            const segmentCount = s.segments?.length ?? 0;
            const hasDetails = Boolean(s.summary || segmentCount || s.status !== "read");

            return (
              <li key={s.id} className="rounded border border-slate-200 text-xs">
                <div className="flex items-start gap-1 p-2">
                  <button
                    type="button"
                    className="mt-0.5 shrink-0 rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-40"
                    disabled={!hasDetails}
                    aria-expanded={sourceOpen}
                    aria-label={sourceOpen ? "收起资料详情" : "展开资料详情"}
                    onClick={() => toggleSource(s.id)}
                  >
                    {sourceOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                  </button>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <button
                        type="button"
                        className="min-w-0 text-left font-medium text-slate-800 hover:text-indigo-700"
                        onClick={() => hasDetails && toggleSource(s.id)}
                      >
                        <span className="line-clamp-2">{s.title}</span>
                      </button>
                      <button
                        type="button"
                        className="shrink-0 rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-40"
                        disabled={busy}
                        aria-label={`删除 ${s.title}`}
                        onClick={() => void handleDelete(s)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className={`mt-0.5 ${statusBadgeClass(s.status)}`}>
                      {STATUS_LABEL[s.status] ?? s.status}
                      {segmentCount > 0 && !sourceOpen ? (
                        <span className="text-slate-400"> · {segmentCount} 个解析片段</span>
                      ) : null}
                      {(s.chunk_count ?? 0) > 0 ? (
                        <span className="text-slate-400"> · {s.chunk_count} 个全文分块</span>
                      ) : null}
                    </div>
                  </div>
                </div>

                {sourceOpen ? (
                  <div className="space-y-2 border-t border-slate-100 px-2 pb-2 pt-1.5">
                    {s.summary ? <p className="text-slate-600">{s.summary}</p> : null}
                    {(s.used_stages?.length ?? 0) > 0 ? (
                      <p className="text-[10px] text-emerald-700">
                        已用于：{s.used_stages?.map((stage) => STAGE_LABEL[stage] ?? stage).join("、")}
                      </p>
                    ) : null}

                    {segmentCount > 0 ? (
                      <div>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-slate-500 hover:bg-slate-50 hover:text-slate-700"
                          aria-expanded={segmentsOpen}
                          onClick={() => toggleSegments(s.id)}
                        >
                          {segmentsOpen ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronRight className="h-3 w-3" />
                          )}
                          解析片段（{segmentCount}）
                        </button>
                        {segmentsOpen ? (
                          <ul className="mt-1.5 space-y-1.5">
                            {s.segments?.map((seg) => (
                              <li key={seg.id} className="rounded bg-slate-50 p-1.5">
                                <div className="flex items-start justify-between gap-1">
                                  <span className="font-medium text-slate-700">
                                    {SEGMENT_TYPE_LABEL[seg.segment_type] ?? seg.segment_type}
                                  </span>
                                  <span
                                    className={
                                      seg.needs_confirm || seg.confidence < 0.7
                                        ? "shrink-0 text-amber-600"
                                        : "shrink-0 text-slate-400"
                                    }
                                  >
                                    {confidenceLabel(seg.confidence)}
                                  </span>
                                </div>
                                <p className="mt-0.5 text-slate-600">{seg.summary}</p>
                                {seg.locator ? <p className="text-slate-400">{seg.locator}</p> : null}
                                {seg.user_confirmed === true ? (
                                  <p className="mt-1 text-emerald-600">已确认用途</p>
                                ) : seg.user_confirmed === false ? (
                                  <p className="mt-1 text-slate-400">已排除</p>
                                ) : seg.needs_confirm || seg.confidence < 0.7 ? (
                                  <div className="mt-1 flex gap-2">
                                    <button
                                      type="button"
                                      className="text-indigo-600 disabled:opacity-50"
                                      disabled={busy}
                                      onClick={() => void handleConfirmSegment(seg.id, true)}
                                    >
                                      确认
                                    </button>
                                    <button
                                      type="button"
                                      className="text-slate-500 disabled:opacity-50"
                                      disabled={busy}
                                      onClick={() => void handleConfirmSegment(seg.id, false)}
                                    >
                                      否认
                                    </button>
                                  </div>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    ) : null}

                    {s.status !== "read" && s.status !== "indexed" && (s.status === "failed" || !s.reference_file_id) ? (
                      <button
                        type="button"
                        className="text-indigo-600 disabled:opacity-50"
                        disabled={busy}
                        onClick={() => void handleRead(s.id)}
                      >
                        {s.status === "failed" && s.reference_file_id ? "重新索引" : "读取/识别片段"}
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
          </ul>
        </section>

        <section>
          <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            引用（{citations.length}）
          </h4>
          {citationsQuery.isLoading ? <div className="text-xs text-slate-500">加载引用…</div> : null}
          {citationsQuery.isError ? <div className="text-xs text-red-600">引用加载失败</div> : null}
          {!citationsQuery.isLoading && !citations.length ? (
            <p className="text-[11px] text-slate-400">暂无引用；在对话检索结果中勾选后「加入本书」</p>
          ) : null}
          <ul className="space-y-2">
            {citations.map((c) => (
              <li key={c.id} className="rounded border border-slate-200 p-2 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-slate-800 line-clamp-2">{c.title}</p>
                    <p className="mt-0.5 text-[10px] text-slate-500">
                      {(c.authors || []).slice(0, 3).join(", ")}
                      {c.year ? ` · ${c.year}` : ""}
                      {c.external_source || c.source ? ` · ${c.external_source || c.source}` : ""}
                    </p>
                    {c.url ? (
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[10px] text-indigo-600 hover:underline"
                      >
                        打开
                      </a>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="shrink-0 rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-40"
                    disabled={busy}
                    aria-label={`删除引用 ${c.title}`}
                    onClick={() => void handleDeleteCitation(c.id, c.title)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
