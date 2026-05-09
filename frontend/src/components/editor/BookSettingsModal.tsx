import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import toast from "react-hot-toast";

import { updateBook } from "@/api/books";
import { audienceKey, topicKey } from "@/components/editor/SetupView";
import type { Book, CitationStyle } from "@/types/book";

const CITATION_OPTIONS: { value: CitationStyle; label: string }[] = [
  { value: "apa", label: "APA" },
  { value: "mla", label: "MLA" },
  { value: "chicago", label: "Chicago" },
  { value: "gb_t7714", label: "GB/T 7714" },
];

type Props = {
  open: boolean;
  book: Book;
  bookId: string;
  onClose: () => void;
  onSaved: (b: Book) => void;
};

export default function BookSettingsModal({ open, book, bookId, onClose, onSaved }: Props) {
  const [targetAudience, setTargetAudience] = useState("");
  const [discipline, setDiscipline] = useState("");
  const [citation, setCitation] = useState<CitationStyle | "">("");
  const [targetWords, setTargetWords] = useState("80000");
  const [topicBrief, setTopicBrief] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDiscipline(book.discipline ?? "");
    setCitation(book.citation_style ?? "");
    setTargetWords(String(book.target_words ?? 80000));
    setTopicBrief(window.localStorage.getItem(topicKey(bookId)) ?? "");
    const fromApi = book.target_audience?.trim();
    if (fromApi) setTargetAudience(fromApi);
    else setTargetAudience(window.localStorage.getItem(audienceKey(bookId)) ?? "");
  }, [open, book, bookId]);

  async function handleSave() {
    const tw = parseInt(targetWords, 10);
    if (Number.isNaN(tw) || tw < 1000) {
      toast.error("目标字数需为 ≥1000 的数字");
      return;
    }
    setBusy(true);
    try {
      window.localStorage.setItem(topicKey(bookId), topicBrief);
      window.localStorage.setItem(audienceKey(bookId), targetAudience);
      const next = await updateBook(bookId, {
        discipline: discipline.trim() || null,
        target_audience: targetAudience.trim() || null,
        citation_style: citation || null,
        target_words: tw,
      });
      onSaved(next);
      toast.success("书稿设定已保存");
      onClose();
    } catch {
      toast.error("保存失败");
    } finally {
      setBusy(false);
    }
  }

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[320] flex items-center justify-center bg-slate-900/50 px-4 py-8">
      <div className="absolute inset-0" aria-hidden onClick={() => !busy && onClose()} />
      <div className="relative z-[321] max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-lg font-medium text-ink">保存书稿设定</h3>
          <button type="button" className="icon-button h-9 w-9 shrink-0" onClick={onClose} disabled={busy} aria-label="关闭">
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          书名：{book.title || "未命名"} · 类型：{book.book_type === "academic" ? "学术" : "非虚构"}
        </p>

        <div className="mt-5 space-y-4 text-sm">
          <label className="block">
            <span className="text-slate-600">目标读者</span>
            <input className="input mt-1 w-full" value={targetAudience} onChange={(e) => setTargetAudience(e.target.value)} />
          </label>
          <label className="block">
            <span className="text-slate-600">学科领域</span>
            <input className="input mt-1 w-full" value={discipline} onChange={(e) => setDiscipline(e.target.value)} />
          </label>
          <label className="block">
            <span className="text-slate-600">引用格式</span>
            <select
              className="input mt-1 w-full"
              value={citation}
              onChange={(e) => setCitation(e.target.value as CitationStyle | "")}
            >
              <option value="">无需引用</option>
              {CITATION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-slate-600">目标字数</span>
            <input className="input mt-1 w-full" type="number" min={1000} value={targetWords} onChange={(e) => setTargetWords(e.target.value)} />
          </label>
          <label className="block">
            <span className="text-slate-600">主题要点</span>
            <textarea className="input mt-1 min-h-[120px] w-full" value={topicBrief} onChange={(e) => setTopicBrief(e.target.value)} />
          </label>
        </div>

        <div className="mt-8 flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={() => void handleSave()} disabled={busy}>
            {busy ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
