import { Copy, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

type Props = {
  open: boolean;
  bookTitle: string;
  hasOutline: boolean;
  chapterCount: number;
  busy?: boolean;
  onClose: () => void;
  onConfirm: (copyOutline: boolean) => void;
};

export default function DuplicateBookDialog({
  open,
  bookTitle,
  hasOutline,
  chapterCount,
  busy = false,
  onClose,
  onConfirm,
}: Props) {
  const [copyOutline, setCopyOutline] = useState(false);

  useEffect(() => {
    if (!open) return;
    setCopyOutline(hasOutline);
  }, [open, hasOutline]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[400] flex items-center justify-center bg-slate-900/50 px-4 py-8">
      <div className="absolute inset-0" aria-hidden onClick={() => !busy && onClose()} />
      <div className="relative z-[401] w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-lg font-medium text-ink">基于本书新建</h3>
          <button
            type="button"
            className="icon-button h-9 w-9 shrink-0"
            onClick={onClose}
            disabled={busy}
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="mt-2 text-xs text-slate-500">原书：{bookTitle || "未命名"}</p>
        <p className="mt-3 text-sm leading-relaxed text-slate-600">
          将复制书稿设定与用户资料，原书不会改变。章节正文、写作规则、审校结果与图表不会复制。
        </p>

        <label className="mt-4 flex cursor-pointer items-start gap-2.5 rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-3 text-sm">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={copyOutline}
            disabled={busy || !hasOutline}
            onChange={(e) => setCopyOutline(e.target.checked)}
          />
          <span>
            <span className="font-medium text-slate-700">同时复制当前大纲</span>
            <span className="mt-0.5 block text-xs text-slate-500">
              {hasOutline
                ? `复制 ${chapterCount} 个章节的标题、摘要与小节结构，不含已写正文。`
                : "当前书稿尚无大纲，无法复制。"}
            </span>
          </span>
        </label>

        <div className="mt-6 flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary inline-flex items-center gap-1.5"
            disabled={busy}
            onClick={() => onConfirm(copyOutline)}
          >
            <Copy className="h-4 w-4" />
            {busy ? "创建中…" : "创建新书"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
