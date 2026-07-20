import { Loader2, Wand2 } from "lucide-react";

import type { WorkspaceFinding } from "@/features/review/reviewWorkspaceApi";
import { PRODUCT_DIMENSION_LABEL, type ProductDimension } from "@/features/review/reviewWorkspaceApi";

const TIER_LABEL = { must_fix: "必改", needs_verification: "待核验", suggest: "建议", observe: "观察" } as const;
const FIX_CAPABILITY_LABEL: Record<string, string> = {
  preview_apply: "可预览应用",
  choice_then_apply: "需选择处理",
  manual_only: "需人工处理",
  observe_only: "仅观察",
};
const IMPACT_LABEL: Record<string, string> = {
  sentence: "句子",
  paragraph: "段落",
  section: "小节",
  chapter: "章节",
  book: "全书",
};

const STATUS_LABEL: Record<string, string> = {
  open: "待处理",
  applied_pending_recheck: "待复查",
  resolved: "已处理",
  dismissed: "已忽略",
};

type Props = {
  findings: WorkspaceFinding[];
  selectedId: string | null;
  onSelect: (finding: WorkspaceFinding) => void;
  showObserve: boolean;
  onToggleObserve: () => void;
  tierFilter: string | null;
  batchPreviewableCount?: number;
  batchPreviewBusy?: boolean;
  onBatchPreview?: () => void;
};

export default function ReviewFindingList({
  findings,
  selectedId,
  onSelect,
  showObserve,
  onToggleObserve,
  tierFilter,
  batchPreviewableCount = 0,
  batchPreviewBusy = false,
  onBatchPreview,
}: Props) {
  const mustFix = findings.filter((f) => f.tier === "must_fix");
  const needsVerification = findings.filter((f) => f.tier === "needs_verification");
  const suggest = findings.filter((f) => f.tier === "suggest");
  const observe = findings.filter((f) => f.tier === "observe");

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="mb-2 flex justify-end">
          <button
            type="button"
            aria-label="batch-preview-findings"
            className="inline-flex h-8 items-center gap-1.5 rounded border border-teal-200 bg-teal-50 px-2.5 text-[11px] font-medium text-teal-900 hover:bg-teal-100 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!batchPreviewableCount || batchPreviewBusy}
            onClick={onBatchPreview}
            title="Generate previews for low-risk locatable findings"
          >
            {batchPreviewBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wand2 className="h-3.5 w-3.5" />}
            批量生成预览
            {batchPreviewableCount > 0 ? <span>({batchPreviewableCount})</span> : null}
          </button>
        </div>
        <h3 className="text-sm font-semibold text-ink">问题列表</h3>
        <p className="mt-1 text-[11px] text-slate-500">展示问题、维度、影响范围与依据来源。</p>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {!tierFilter || tierFilter === "must_fix" ? (
          <FindingSection title={`必改 (${mustFix.length})`} items={mustFix} selectedId={selectedId} onSelect={onSelect} />
        ) : null}
        {!tierFilter || tierFilter === "needs_verification" ? (
          <FindingSection title={`待核验 (${needsVerification.length})`} items={needsVerification} selectedId={selectedId} onSelect={onSelect} muted />
        ) : null}
        {!tierFilter || tierFilter === "suggest" ? (
          <FindingSection title={`建议 (${suggest.length})`} items={suggest} selectedId={selectedId} onSelect={onSelect} muted />
        ) : null}
        {(!tierFilter || tierFilter === "observe") && !showObserve && tierFilter !== "observe" ? (
          <button type="button" className="text-[11px] text-slate-500 hover:text-slate-800" onClick={onToggleObserve}>
            展开观察项 ({observe.length})
          </button>
        ) : null}
        {showObserve || tierFilter === "observe" ? (
          <FindingSection title={`观察 (${observe.length})`} items={observe} selectedId={selectedId} onSelect={onSelect} muted />
        ) : null}
        {findings.length === 0 ? (
          <p className="rounded border border-slate-100 bg-slate-50 p-4 text-xs text-slate-500">暂无待处理审校项</p>
        ) : null}
      </div>
    </div>
  );
}

function FindingSection({
  title,
  items,
  selectedId,
  onSelect,
  muted,
}: {
  title: string;
  items: WorkspaceFinding[];
  selectedId: string | null;
  onSelect: (finding: WorkspaceFinding) => void;
  muted?: boolean;
}) {
  if (!items.length) return null;
  return (
    <div className="mb-4">
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-slate-400">{title}</p>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={`${item.source}-${item.id}`}>
            <button
              type="button"
              className={`w-full rounded-lg border p-3 text-left text-xs transition ${
                selectedId === item.id ? "border-teal-300 bg-teal-50" : muted ? "border-slate-100 bg-slate-50 hover:border-slate-200" : "border-slate-200 bg-white hover:border-teal-200"
              }`}
              onClick={() => onSelect(item)}
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-medium text-ink">{item.title}</span>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px]">{TIER_LABEL[item.tier]}</span>
                {item.product_dimension ? (
                  <span className="rounded bg-violet-50 px-1.5 py-0.5 text-[10px] text-violet-800">
                    {PRODUCT_DIMENSION_LABEL[item.product_dimension as ProductDimension] ?? item.product_dimension}
                  </span>
                ) : null}
                {item.fix_capability ? (
                  <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] text-indigo-800">
                    {FIX_CAPABILITY_LABEL[item.fix_capability] ?? item.fix_capability}
                  </span>
                ) : null}
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px]">{STATUS_LABEL[item.status] ?? item.status}</span>
              </div>
              {item.impact_scope ? (
                <p className="mt-1 text-[10px] text-slate-500">影响范围：{IMPACT_LABEL[item.impact_scope] ?? item.impact_scope}</p>
              ) : null}
              {item.quote ? <p className="mt-1 line-clamp-2 text-[10px] italic text-slate-600">「{item.quote}」</p> : null}
              {!item.locatable && item.chapter_index != null ? (
                <p className="mt-1 text-[10px] text-amber-700">需人工复核（无法自动定位）</p>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
