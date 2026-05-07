import { Sparkles } from "lucide-react";

type Props = {
  onAiAssist: () => void;
  onManual: () => void;
};

export default function EmptyChapterState({ onAiAssist, onManual }: Props) {
  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center rounded-2xl border border-dashed border-violet-200 bg-gradient-to-b from-violet-50/80 to-white px-6 py-16 text-center">
      <span className="rounded-full bg-violet-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-violet-700">
        本章正文
      </span>
      <div className="mt-6 flex h-14 w-14 items-center justify-center rounded-full bg-violet-600 text-white shadow-lg shadow-violet-500/30">
        <Sparkles className="h-7 w-7" />
      </div>
      <h2 className="mt-6 text-2xl font-semibold text-ink">开始撰写本章</h2>
      <p className="mt-2 max-w-md text-sm text-slate-600">
        本章尚无正文。可使用 AI 生成初稿，或直接手动撰写。
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
        <button type="button" className="btn-primary inline-flex items-center gap-2 px-6" onClick={onAiAssist}>
          <Sparkles className="h-4 w-4" />
          AI 协助生成
        </button>
        <button
          type="button"
          className="text-sm font-medium text-ink underline-offset-4 hover:underline"
          onClick={onManual}
        >
          手动撰写
        </button>
      </div>
    </div>
  );
}
