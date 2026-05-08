import { FileText, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { searchReferences } from "@/api/references";

type Props = {
  open: boolean;
  bookId: string;
  chapterTitle: string;
  onClose: () => void;
};

export default function ChapterReferenceDrawer({ open, bookId, chapterTitle, onClose }: Props) {
  const [snippets, setSnippets] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !chapterTitle.trim()) {
      setSnippets([]);
      setErr(null);
      return;
    }
    setLoading(true);
    setErr(null);
    searchReferences(bookId, { query: chapterTitle.trim(), top_k: 8 })
      .then((r) => setSnippets(r.snippets ?? []))
      .catch((e) => setErr(e instanceof Error ? e.message : "检索失败"))
      .finally(() => setLoading(false));
  }, [open, bookId, chapterTitle]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-y-0 right-0 z-[280] flex w-full max-w-md flex-col border-l border-slate-200 bg-white/95 shadow-2xl backdrop-blur-md">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="h-4 w-4 shrink-0 text-slate-500" />
          <span className="truncate text-sm font-semibold text-ink">参考资料</span>
        </div>
        <button type="button" className="icon-button h-9 w-9 shrink-0" aria-label="关闭" onClick={onClose}>
          <X className="h-4 w-4" />
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto p-4 text-sm">
        <p className="mb-3 text-xs text-slate-500">检索查询：{chapterTitle || "—"}</p>
        {loading ? <p className="text-slate-500">检索中…</p> : null}
        {err ? <p className="text-rose-600">{err}</p> : null}
        {!loading && !err && snippets.length === 0 ? <p className="text-slate-400">暂无匹配片段</p> : null}
        <ul className="space-y-3">
          {snippets.map((s, i) => (
            <li key={i} className="rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2 text-xs leading-relaxed text-slate-700">
              {s}
            </li>
          ))}
        </ul>
      </div>
    </div>,
    document.body,
  );
}
