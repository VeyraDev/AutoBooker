import type { WorkspaceFinding } from "@/features/review/reviewWorkspaceApi";
import { PRODUCT_DIMENSION_LABEL, type ProductDimension } from "@/features/review/reviewWorkspaceApi";

const TIER_LABEL = { must_fix: "必改", suggest: "建议", observe: "观察" } as const;
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
};

export default function ReviewFindingList({
  findings,
  selectedId,
  onSelect,
  showObserve,
  onToggleObserve,
  tierFilter,
}: Props) {
  const mustFix = findings.filter((f) => f.tier === "must_fix");
  const suggest = findings.filter((f) => f.tier === "suggest");
  const observe = findings.filter((f) => f.tier === "observe");

  return (
    <div className="flex h-full min-h-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-ink">问题列表</h3>
        <p className="mt-1 text-[11px] text-slate-500">展示问题、维度、影响范围与依据来源。</p>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {!tierFilter || tierFilter === "must_fix" ? (
          <FindingSection title={`必改 (${mustFix.length})`} items={mustFix} selectedId={selectedId} onSelect={onSelect} />
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
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px]">{STATUS_LABEL[item.status] ?? item.status}</span>
              </div>
              {item.impact_scope ? (
                <p className="mt-1 text-[10px] text-slate-500">影响范围：{IMPACT_LABEL[item.impact_scope] ?? item.impact_scope}</p>
              ) : null}
              {item.quote ? <p className="mt-1 line-clamp-2 text-[10px] italic text-slate-600">「{item.quote}」</p> : null}
              {!item.locatable && item.source === "chapter" ? (
                <p className="mt-1 text-[10px] text-amber-700">需人工复核（无法自动定位）</p>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
