import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { ProductDimension, ReviewTask } from "@/features/review/reviewWorkspaceApi";
import { PRODUCT_DIMENSION_LABEL } from "@/features/review/reviewWorkspaceApi";

const TIER_FILTERS = [
  { id: "must_fix", label: "必须处理" },
  { id: "needs_verification", label: "待核验" },
  { id: "suggest", label: "建议处理" },
  { id: "observe", label: "可选观察" },
  { id: "resolved", label: "已处理" },
  { id: "dismissed", label: "已忽略" },
] as const;

const DIMENSIONS = Object.keys(PRODUCT_DIMENSION_LABEL) as ProductDimension[];

type Props = {
  chapterIndexes: number[];
  selectedChapter: number | null;
  selectedTier: string | null;
  selectedDimension: ProductDimension | null;
  onSelectChapter: (index: number | null) => void;
  onSelectTier: (tier: string | null) => void;
  onSelectDimension: (dim: ProductDimension | null) => void;
  mustFixCount: number;
  suggestCount: number;
  observeCount: number;
  needsVerificationCount?: number;
  runStatus: string | null;
  latestTask: ReviewTask | null;
  running: boolean;
  customPrompt: string;
  onCustomPromptChange: (v: string) => void;
  onRunBook: () => void;
  onRunChapter: () => void;
  onRunCustom: () => void;
  onBack: () => void;
  onCompleteBook?: () => void;
  completing?: boolean;
  showCompleteBook?: boolean;
};

export default function ReviewScopeNav({
  chapterIndexes,
  selectedChapter,
  selectedTier,
  selectedDimension,
  onSelectChapter,
  onSelectTier,
  onSelectDimension,
  mustFixCount,
  suggestCount,
  observeCount,
  needsVerificationCount = 0,
  runStatus,
  latestTask,
  running,
  customPrompt,
  onCustomPromptChange,
  onRunBook,
  onRunChapter,
  onRunCustom,
  onBack,
  onCompleteBook,
  completing,
  showCompleteBook,
}: Props) {
  const [taskOpen, setTaskOpen] = useState(false);
  const [customOpen, setCustomOpen] = useState(false);

  return (
    <aside className="flex h-full min-h-0 w-[260px] shrink-0 flex-col border-r border-slate-200 bg-slate-50">
      <div className="border-b border-slate-200 p-4">
        <button type="button" className="text-xs text-slate-500 hover:text-slate-800" onClick={onBack}>
          ← 返回写作
        </button>
        <h2 className="mt-2 text-base font-semibold text-ink">审校工作台</h2>
      </div>

      <div className="space-y-2 border-b border-slate-200 p-3 text-xs">
        <div className="flex justify-between"><span className="text-slate-500">必改</span><span className="font-semibold text-red-700">{mustFixCount}</span></div>
        <div className="flex justify-between"><span className="text-slate-500">待核验</span><span className="font-medium text-sky-800">{needsVerificationCount}</span></div>
        <div className="flex justify-between"><span className="text-slate-500">建议</span><span className="font-medium text-amber-800">{suggestCount}</span></div>
        <div className="flex justify-between"><span className="text-slate-500">观察</span><span className="font-medium text-slate-600">{observeCount}</span></div>
        {runStatus ? <p className="rounded bg-white px-2 py-1 text-[10px] text-slate-600">最近运行：{runStatus}</p> : null}
      </div>

      {latestTask?.summary_text ? (
        <div className="border-b border-slate-200 p-3">
          <button type="button" className="flex w-full items-center gap-1 text-[11px] font-medium text-slate-700" onClick={() => setTaskOpen((v) => !v)}>
            {taskOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            本次审校任务单
          </button>
          {taskOpen ? (
            <pre className="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap rounded border border-slate-200 bg-white p-2 text-[10px] text-slate-600">
              {latestTask.summary_text}
            </pre>
          ) : null}
        </div>
      ) : null}

      <div className="space-y-2 border-b border-slate-200 p-3">
        <button type="button" className="btn-primary flex h-9 w-full items-center justify-center gap-2 text-xs" disabled={running} onClick={onRunBook}>
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          运行全书审校
        </button>
        <button type="button" className="btn-secondary flex h-9 w-full items-center justify-center text-xs disabled:opacity-50" disabled={running || selectedChapter == null} onClick={onRunChapter}>
          运行当前章审校
        </button>
        {showCompleteBook && onCompleteBook ? (
          <button type="button" className="btn-secondary flex h-9 w-full items-center justify-center text-xs" disabled={completing} onClick={() => void onCompleteBook()}>
            {completing ? "处理中…" : "完成全书"}
          </button>
        ) : null}
      </div>

      <div className="border-b border-slate-200 p-3">
        <button type="button" className="flex w-full items-center gap-1 text-[11px] font-medium text-slate-700" onClick={() => setCustomOpen((v) => !v)}>
          {customOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          专项审校
        </button>
        {customOpen ? (
          <div className="mt-2 space-y-2">
            <textarea
              className="input min-h-[72px] w-full text-xs"
              placeholder="例如：只看这章有没有跑题"
              value={customPrompt}
              onChange={(e) => onCustomPromptChange(e.target.value)}
            />
            <button type="button" className="btn-secondary h-8 w-full text-xs" disabled={running || !customPrompt.trim()} onClick={onRunCustom}>
              运行专项审校
            </button>
          </div>
        ) : null}
      </div>

      <div className="border-b border-slate-200 p-3">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-slate-400">级别筛选</p>
        <div className="flex flex-wrap gap-1">
          <FilterChip active={selectedTier == null} label="全部" onClick={() => onSelectTier(null)} />
          {TIER_FILTERS.map((t) => (
            <FilterChip key={t.id} active={selectedTier === t.id} label={t.label} onClick={() => onSelectTier(t.id)} />
          ))}
        </div>
      </div>

      <div className="border-b border-slate-200 p-3">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-slate-400">审校维度</p>
        <div className="max-h-28 space-y-1 overflow-y-auto">
          <FilterChip active={selectedDimension == null} label="全部维度" onClick={() => onSelectDimension(null)} />
          {DIMENSIONS.map((d) => (
            <FilterChip key={d} active={selectedDimension === d} label={PRODUCT_DIMENSION_LABEL[d]} onClick={() => onSelectDimension(d)} />
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        <ScopeBtn active={selectedChapter == null} onClick={() => onSelectChapter(null)}>全书</ScopeBtn>
        {chapterIndexes.map((idx) => (
          <ScopeBtn key={idx} active={selectedChapter === idx} onClick={() => onSelectChapter(idx)}>第 {idx} 章</ScopeBtn>
        ))}
      </div>
    </aside>
  );
}

function FilterChip({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      className={`rounded px-2 py-1 text-[10px] ${active ? "bg-teal-100 text-teal-900" : "bg-white text-slate-600 hover:bg-slate-100"}`}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function ScopeBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      className={`mb-1 w-full rounded px-3 py-2 text-left text-xs ${active ? "bg-teal-50 font-medium text-teal-900" : "text-slate-700 hover:bg-white"}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
