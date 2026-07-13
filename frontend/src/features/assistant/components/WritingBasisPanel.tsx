import type { WritingBasis } from "@/features/assistant/api/assistantApi";

type Props = {
  basis: WritingBasis | null | undefined;
  loading?: boolean;
  onPatch: (patch: Partial<WritingBasis>) => void;
  onConfirm: () => void;
  confirming?: boolean;
};

const TEXT_FIELDS: Array<{ key: keyof WritingBasis; label: string }> = [
  { key: "direction", label: "书稿方向" },
  { key: "book_promise", label: "书稿承诺" },
  { key: "target_readers", label: "目标读者" },
  { key: "reader_outcome", label: "读者收益" },
  { key: "scope", label: "内容范围" },
  { key: "depth", label: "专业深度" },
  { key: "voice", label: "语言风格" },
];

const LIST_FIELDS: Array<{ key: keyof WritingBasis; label: string }> = [
  { key: "must_avoid", label: "禁止事项" },
  { key: "must_keep", label: "必须保留" },
  { key: "material_policy", label: "资料使用规则" },
  { key: "open_questions", label: "待确认问题" },
];

export default function WritingBasisPanel({ basis, loading, onPatch, onConfirm, confirming }: Props) {
  if (loading) {
    return <div className="p-4 text-sm text-slate-500">正在加载写作依据…</div>;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 px-3 py-2">
        <h3 className="text-sm font-semibold text-slate-800">当前写作依据</h3>
        <p className="text-xs text-slate-500">助手会随对话更新；你也可以直接编辑。</p>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">
        {TEXT_FIELDS.map(({ key, label }) => (
          <label key={key} className="block">
            <span className="text-xs text-slate-500">{label}</span>
            <textarea
              className="mt-1 w-full rounded border border-slate-200 p-2 text-sm"
              rows={key === "direction" || key === "book_promise" ? 2 : 1}
              value={String(basis?.[key] ?? "")}
              onChange={(e) => onPatch({ [key]: e.target.value })}
            />
          </label>
        ))}
        {LIST_FIELDS.map(({ key, label }) => (
          <label key={key} className="block">
            <span className="text-xs text-slate-500">{label}</span>
            <textarea
              className="mt-1 w-full rounded border border-slate-200 p-2 text-sm"
              rows={2}
              value={((basis?.[key] as string[] | undefined) ?? []).join("\n")}
              onChange={(e) =>
                onPatch({
                  [key]: e.target.value
                    .split("\n")
                    .map((x) => x.trim())
                    .filter(Boolean),
                })
              }
            />
          </label>
        ))}
      </div>
      <div className="border-t border-slate-200 p-3">
        <button
          type="button"
          className="w-full rounded bg-brand px-3 py-2 text-sm text-white disabled:opacity-50"
          disabled={confirming || basis?.status === "confirmed"}
          onClick={onConfirm}
        >
          {basis?.status === "confirmed" ? "写作依据已确认" : confirming ? "确认中…" : "确认写作依据"}
        </button>
      </div>
    </div>
  );
}
