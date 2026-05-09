import { Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

export type AddChapterFormValues = {
  title: string;
  summary: string;
  keyPoints: string[];
  mode: "ai" | "manual";
};

type Props = {
  open: boolean;
  onClose: () => void;
  onSubmit: (values: AddChapterFormValues) => void;
};

export default function AddChapterDialog({ open, onClose, onSubmit }: Props) {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [keyPoints, setKeyPoints] = useState<string[]>([]);
  const [draftPoint, setDraftPoint] = useState("");

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setSummary("");
    setKeyPoints([]);
    setDraftPoint("");
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  function addPoint() {
    const t = draftPoint.trim();
    if (!t) return;
    setKeyPoints((prev) => [...prev, t]);
    setDraftPoint("");
  }

  function removePoint(i: number) {
    setKeyPoints((prev) => prev.filter((_, j) => j !== i));
  }

  const portal = (
    <div className="fixed inset-0 z-[400] flex items-center justify-center bg-slate-900/50 px-4 py-8">
      <div
        className="absolute inset-0"
        aria-hidden
        onClick={onClose}
      />
      <div className="relative z-[401] w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-lg font-medium text-ink">新增章节</h3>
          <button type="button" className="icon-button h-9 w-9 shrink-0" onClick={onClose} aria-label="关闭">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 space-y-4 text-sm">
          <label className="block">
            <span className="text-slate-600">章节标题</span>
            <input className="input mt-1 w-full" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="请输入标题" />
          </label>
          <label className="block">
            <span className="text-slate-600">摘要（可选）</span>
            <textarea className="input mt-1 min-h-[72px] w-full" value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="本章摘要" />
          </label>
          <div>
            <span className="text-slate-600">核心论点（可选）</span>
            <div className="mt-2 flex flex-wrap gap-2">
              {keyPoints.map((p, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-700"
                >
                  {p}
                  <button type="button" className="text-slate-400 hover:text-red-600" onClick={() => removePoint(i)} aria-label="移除">
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="mt-2 flex gap-2">
              <input
                className="input min-w-0 flex-1 text-sm"
                value={draftPoint}
                onChange={(e) => setDraftPoint(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addPoint();
                  }
                }}
                placeholder="输入论点后点击添加"
              />
              <button type="button" className="btn-secondary shrink-0 px-3 text-xs" onClick={addPoint}>
                <Plus className="mr-0.5 inline h-3.5 w-3.5" />
                添加论点
              </button>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button type="button" className="btn-secondary order-2 sm:order-1" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary order-1 sm:order-2"
            disabled={!title.trim()}
            onClick={() =>
              onSubmit({
                title: title.trim(),
                summary: summary.trim(),
                keyPoints,
                mode: "ai",
              })
            }
          >
            AI 协助生成
          </button>
          <button
            type="button"
            className="btn-secondary order-3 border-violet-200 bg-violet-50/80 text-violet-900 hover:bg-violet-100"
            disabled={!title.trim()}
            onClick={() =>
              onSubmit({
                title: title.trim(),
                summary: summary.trim(),
                keyPoints,
                mode: "manual",
              })
            }
          >
            手动写作
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(portal, document.body);
}
