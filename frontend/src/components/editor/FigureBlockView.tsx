import { NodeViewWrapper } from "@tiptap/react";
import type { NodeViewProps } from "@tiptap/react";
import axios from "axios";
import { Maximize2, RefreshCw, Upload, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import toast from "react-hot-toast";

import {
  formatFigureLabel,
  generateFigure,
  resolveFigureUrl,
  shortenFigureCaption,
  uploadFigure,
  type FigureType,
} from "@/api/figures";
import { useFigureBlockContext } from "@/contexts/FigureBlockContext";

function figureApiErrorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) {
    if (e.code === "ECONNABORTED") {
      return "生成超时（图像服务较慢），请稍后重试";
    }
    const detail = e.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return e instanceof Error ? e.message : fallback;
}

function FigureImageModal({
  src,
  label,
  onClose,
}: {
  src: string;
  label: string;
  onClose: () => void;
}) {
  const [zoom, setZoom] = useState(1);

  return createPortal(
    <div
      className="figure-fullscreen-overlay fixed inset-0 z-[9999] flex flex-col bg-black/85"
      role="dialog"
      aria-label={label}
      onClick={onClose}
    >
      <div className="flex items-center justify-between px-4 py-3 text-white">
        <span className="text-sm font-medium">{label}</span>
        <button type="button" className="rounded p-1 hover:bg-white/10" onClick={onClose} aria-label="关闭">
          <X className="h-5 w-5" />
        </button>
      </div>
      <div
        className="flex flex-1 items-center justify-center overflow-auto p-6"
        onClick={(e) => e.stopPropagation()}
        onDoubleClick={(e) => e.stopPropagation()}
      >
        <img
          src={src}
          alt={label}
          className="max-h-full max-w-full object-contain transition-transform duration-150"
          style={{ transform: `scale(${zoom})` }}
          onDoubleClick={() => setZoom((z) => (z >= 2 ? 1 : z + 0.4))}
          onWheel={(e) => {
            e.preventDefault();
            setZoom((z) => Math.min(3, Math.max(0.5, z + (e.deltaY < 0 ? 0.1 : -0.1))));
          }}
        />
      </div>
    </div>,
    document.body,
  );
}

/** 按本章 TipTap 文档中 figureBlock 出现顺序计算图号（图 1-1、图 1-2…） */
function useDisplayFigureLabel(
  figureId: string,
  storedNumber: string,
  chapterIndex: number,
): string {
  const { getFigureOrdinal, figureDocRevision } = useFigureBlockContext();

  return useMemo(() => {
    const ord = getFigureOrdinal(figureId);
    if (chapterIndex > 0 && ord > 0) {
      return formatFigureLabel(`${chapterIndex}-${ord}`);
    }
    return formatFigureLabel(storedNumber);
  }, [figureId, storedNumber, chapterIndex, getFigureOrdinal, figureDocRevision]);
}

export default function FigureBlockView({ node, updateAttributes, selected }: NodeViewProps) {
  const { bookId, chapterIndex, onFigureUpdated, onQuoteFigure, refreshFigureNumbers } =
    useFigureBlockContext();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  /** 本地刷新序号，生成成功后立即换图（不依赖 attrs 落盘或 updated_at） */
  const [imgEpoch, setImgEpoch] = useState(() => Number(node.attrs.fileVersion ?? 0) || Date.now());
  /** 生成后拉取二进制，彻底绕过浏览器对同 URL 的磁盘缓存 */
  const [blobSrc, setBlobSrc] = useState<string | null>(null);

  const figureId = String(node.attrs.figureId ?? "");
  const figureType = String(node.attrs.figureType ?? "figure") as FigureType;
  const figureNumber = String(node.attrs.figureNumber ?? "");
  const caption = String(node.attrs.caption ?? "");
  const status = String(node.attrs.status ?? "pending");
  const fileUrl = String(node.attrs.fileUrl ?? "");
  const fileVersion = Number(node.attrs.fileVersion ?? 0);
  const rawAnnotation = String(node.attrs.rawAnnotation ?? "");
  const isScreenshot = figureType === "screenshot";
  const label = useDisplayFigureLabel(figureId, figureNumber, chapterIndex);
  const cacheKey = imgEpoch || fileVersion || undefined;
  const remoteSrc = resolveFigureUrl(fileUrl, cacheKey);
  const imgSrc = blobSrc ?? remoteSrc;
  const hasFile =
    Boolean(imgSrc) &&
    (status === "generated" || status === "uploaded" || status === "approved");
  const showImage = hasFile && !imgFailed;
  const shortCaption = shortenFigureCaption(caption || rawAnnotation);

  useEffect(() => {
    const v = Number(node.attrs.fileVersion ?? 0);
    if (v > 0) setImgEpoch(v);
  }, [node.attrs.fileVersion]);

  useEffect(() => {
    setImgFailed(false);
  }, [fileUrl, fileVersion, imgEpoch, status, blobSrc]);

  useEffect(() => {
    return () => {
      if (blobSrc?.startsWith("blob:")) URL.revokeObjectURL(blobSrc);
    };
  }, [blobSrc]);

  async function loadFreshImageBlob(url: string) {
    if (!url) return;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    setBlobSrc((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return URL.createObjectURL(blob);
    });
  }

  const applyPatch = useCallback(
    (patch: Record<string, unknown>) => {
      updateAttributes(patch);
      if (figureId) onFigureUpdated(figureId, patch);
    },
    [figureId, onFigureUpdated, updateAttributes],
  );

  async function handleGenerate() {
    if (!bookId || !figureId) {
      toast.error("缺少图表 ID");
      return;
    }
    setBusy(true);
    const loadingToast = toast.loading("正在生成图表，可能需要 1–3 分钟…");
    try {
      const fig = await generateFigure(bookId, figureId);
      const nextVersion = Date.now();
      setImgEpoch(nextVersion);
      const freshUrl = resolveFigureUrl(fig.file_url ?? "", nextVersion);
      applyPatch({
        status: fig.status,
        fileUrl: fig.file_url ?? "",
        figureNumber: fig.figure_number ?? figureNumber,
        caption: fig.caption ?? caption,
        fileVersion: nextVersion,
      });
      if (freshUrl) {
        try {
          await loadFreshImageBlob(freshUrl);
        } catch {
          toast("图表已生成，预览加载较慢，可点击重新生成刷新", { icon: "ℹ️" });
        }
      }
      await refreshFigureNumbers();
      toast.success("图表已生成", { id: loadingToast });
    } catch (e) {
      toast.error(figureApiErrorMessage(e, "生成失败"), { id: loadingToast });
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(file: File) {
    if (!bookId || !figureId) return;
    setBusy(true);
    try {
      const fig = await uploadFigure(bookId, figureId, file);
      const nextVersion = Date.now();
      setImgEpoch(nextVersion);
      const freshUrl = resolveFigureUrl(fig.file_url ?? "", nextVersion);
      applyPatch({
        status: fig.status,
        fileUrl: fig.file_url ?? "",
        figureNumber: fig.figure_number ?? figureNumber,
        fileVersion: nextVersion,
      });
      if (freshUrl) {
        try {
          await loadFreshImageBlob(freshUrl);
        } catch {
          /* 上传已成功，img 标签仍可用 remoteSrc */
        }
      }
      await refreshFigureNumbers();
      toast.success("图片已上传");
    } catch (e) {
      toast.error(figureApiErrorMessage(e, "上传失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <NodeViewWrapper
      className={`figure-block my-4 ${selected ? "ring-2 ring-violet-200 rounded-xl" : ""}`}
      data-figure-id={figureId}
    >
      <div className="relative rounded-xl border border-slate-200 bg-slate-50/80">
        <div className="absolute left-2 top-2 z-10 flex gap-1">
          {!isScreenshot && status !== "pending" ? (
            <button
              type="button"
              title="重新生成"
              disabled={busy}
              className="rounded-md bg-white/90 p-1.5 text-slate-600 shadow-sm hover:bg-violet-50 hover:text-violet-800 disabled:opacity-50"
              onClick={() => void handleGenerate()}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />
            </button>
          ) : null}
          <button
            type="button"
            title={isScreenshot ? "上传图片" : "上传替换"}
            disabled={busy}
            className="rounded-md bg-white/90 p-1.5 text-slate-600 shadow-sm hover:bg-violet-50 hover:text-violet-800 disabled:opacity-50"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="h-3.5 w-3.5" />
          </button>
          {showImage ? (
            <button
              type="button"
              title="全屏"
              className="rounded-md bg-white/90 p-1.5 text-slate-600 shadow-sm hover:bg-violet-50 hover:text-violet-800"
              onClick={() => setFullscreen(true)}
            >
              <Maximize2 className="h-3.5 w-3.5" />
            </button>
          ) : null}
          {onQuoteFigure && figureId ? (
            <button
              type="button"
              title="引用到 AI 助手"
              className="rounded-md bg-white/90 px-2 py-1 text-[10px] text-slate-600 shadow-sm hover:bg-violet-50"
              onClick={() => onQuoteFigure(figureId, rawAnnotation || caption)}
            >
              引用
            </button>
          ) : null}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleUpload(f);
            e.target.value = "";
          }}
        />

        <div className="px-3 pt-2 text-center text-xs font-medium text-slate-600">{label}</div>

        <div className="relative flex min-h-[140px] items-center justify-center p-4">
          {showImage ? (
            <img
              key={`${figureId}-${imgEpoch}`}
              src={imgSrc}
              alt={shortCaption || label}
              className="max-h-[360px] w-full cursor-zoom-in object-contain"
              onDoubleClick={() => setFullscreen(true)}
              onError={() => setImgFailed(true)}
            />
          ) : (
            <div className="flex w-full flex-col items-center gap-3 rounded-lg border border-dashed border-slate-300 bg-slate-100/80 px-4 py-8 text-center">
              {imgFailed ? (
                <p className="text-xs text-amber-700">图片加载失败，请重新生成或上传替换</p>
              ) : (
                <p className="line-clamp-4 text-xs leading-relaxed text-slate-500">
                  {shortCaption || "待生成图表"}
                </p>
              )}
              {!isScreenshot ? (
                <button
                  type="button"
                  disabled={busy}
                  className="btn-primary h-8 px-4 text-xs disabled:opacity-50"
                  onClick={() => void handleGenerate()}
                >
                  {busy ? "生成中…" : imgFailed ? "重新生成" : "生成"}
                </button>
              ) : (
                <button
                  type="button"
                  disabled={busy}
                  className="btn-primary h-8 px-4 text-xs disabled:opacity-50"
                  onClick={() => fileInputRef.current?.click()}
                >
                  上传图片
                </button>
              )}
            </div>
          )}
        </div>

        {showImage && shortCaption ? (
          <p className="border-t border-slate-200/80 px-3 py-2 text-center text-xs text-slate-600">
            图解：{shortCaption}
          </p>
        ) : null}
      </div>

      {fullscreen && showImage ? (
        <FigureImageModal src={imgSrc} label={label} onClose={() => setFullscreen(false)} />
      ) : null}
    </NodeViewWrapper>
  );
}
