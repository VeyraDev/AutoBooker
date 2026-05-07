import { useEffect, useState } from "react";
import toast from "react-hot-toast";

import { putOutline } from "@/api/outline";
import type { OutlineChapter, OutlineSection } from "@/types/outline";

type Props = {
  bookId: string;
  chapter: OutlineChapter;
  onPatched: () => void;
  /** setup：全书「开始写作」进入写作阶段；chapter：单章未撰写时进入正文入口 */
  variant?: "setup" | "chapter";
  onStartWriting: () => void;
  busy?: boolean;
};

export default function ChapterDetailView({
  bookId,
  chapter,
  onPatched,
  onStartWriting,
  variant = "setup",
  busy,
}: Props) {
  const [title, setTitle] = useState(chapter.title);
  const [summary, setSummary] = useState(chapter.summary ?? "");
  const [keyPoints, setKeyPoints] = useState<string[]>(chapter.key_points ?? []);
  const [kpDraft, setKpDraft] = useState("");
  const [est, setEst] = useState(String(chapter.estimated_words ?? 3000));
  const [sections, setSections] = useState<OutlineSection[]>(chapter.sections ?? []);

  useEffect(() => {
    setTitle(chapter.title);
    setSummary(chapter.summary ?? "");
    setKeyPoints(chapter.key_points ?? []);
    setEst(String(chapter.estimated_words ?? 3000));
    setSections(chapter.sections ?? []);
  }, [chapter]);

  async function save() {
    const n = parseInt(est, 10);
    if (Number.isNaN(n) || n < 100) {
      toast.error("预估字数无效");
      return;
    }
    await putOutline(bookId, {
      chapters: [
        {
          index: chapter.index,
          title: title.trim(),
          summary: summary.trim() || null,
          key_points: keyPoints,
          estimated_words: n,
          sections,
        },
      ],
    });
    onPatched();
    toast.success("大纲已更新");
  }

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-medium uppercase text-violet-600">
          {variant === "chapter" ? "大纲就绪 · 未撰写" : "大纲就绪"}
        </p>
        <h2 className="mt-1 text-xl font-medium text-ink">第 {chapter.index} 章 · 细则编辑</h2>
        <p className="mt-1 text-sm text-slate-500">
          {variant === "chapter"
            ? "可修改本章标题、摘要与要点；确认后点击下方「开始写作」进入本章正文创作。"
            : "确认全书结构后，点击下方「开始写作」进入正文阶段。"}
        </p>
      </div>

      <label className="block text-sm">
        <span className="text-slate-600">章节标题</span>
        <input className="input mt-1" value={title} onChange={(e) => setTitle(e.target.value)} onBlur={() => save()} />
      </label>

      <label className="block text-sm">
        <span className="text-slate-600">摘要</span>
        <textarea className="input mt-1 min-h-[100px]" value={summary} onChange={(e) => setSummary(e.target.value)} onBlur={() => save()} />
      </label>

      <div>
        <span className="text-sm text-slate-600">核心论点</span>
        <div className="mt-2 flex flex-wrap gap-2">
          {keyPoints.map((k) => (
            <span
              key={k}
              className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700"
            >
              {k}
              <button
                type="button"
                className="text-rose-600"
                onClick={() => setKeyPoints((prev) => prev.filter((x) => x !== k))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <div className="mt-2 flex gap-2">
          <input
            className="input flex-1 py-1 text-sm"
            value={kpDraft}
            onChange={(e) => setKpDraft(e.target.value)}
            placeholder="新增论点后回车"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                const v = kpDraft.trim();
                if (!v) return;
                setKeyPoints((p) => [...p, v]);
                setKpDraft("");
                void save();
              }
            }}
          />
        </div>
      </div>

      <label className="block text-sm">
        <span className="text-slate-600">预估字数</span>
        <input
          type="number"
          min={100}
          className="input mt-1"
          value={est}
          onChange={(e) => setEst(e.target.value)}
          onBlur={() => save()}
        />
      </label>

      <div>
        <span className="text-sm text-slate-600">小节结构</span>
        <div className="mt-2 space-y-2">
          {sections.map((s, i) => (
            <div key={`${s.title}-${i}`} className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
              <input
                className="input mb-2 py-1 text-sm font-medium"
                value={s.title}
                onChange={(e) => {
                  const next = [...sections];
                  next[i] = { ...next[i], title: e.target.value };
                  setSections(next);
                }}
                onBlur={() => save()}
              />
              <textarea
                className="input py-1 text-xs"
                value={s.summary}
                onChange={(e) => {
                  const next = [...sections];
                  next[i] = { ...next[i], summary: e.target.value };
                  setSections(next);
                }}
                onBlur={() => save()}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-slate-200 pt-6">
        <button type="button" className="btn-primary w-full sm:w-auto" disabled={busy} onClick={() => onStartWriting()}>
          开始写作
        </button>
      </div>
    </div>
  );
}
