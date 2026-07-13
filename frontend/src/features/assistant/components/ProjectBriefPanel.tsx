import type { IntakeState } from "@/features/intake/api/intakeApi";

type Props = {
  intake: IntakeState | null | undefined;
  bookTitle: string;
  loading?: boolean;
  proceeding?: boolean;
  onProceed: () => void;
  onOpenAdvanced: () => void;
};

export default function ProjectBriefPanel({
  intake,
  bookTitle,
  loading,
  proceeding,
  onProceed,
  onOpenAdvanced,
}: Props) {
  if (loading) {
    return <div className="p-4 text-sm text-slate-500">加载项目信息…</div>;
  }

  const goal = intake?.raw_goal_text?.trim() || "（尚未填写创作意图）";

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 px-3 py-2">
        <h3 className="text-sm font-semibold text-slate-800">项目要点</h3>
        <p className="text-xs text-slate-500">当前书稿：{bookTitle}</p>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">
        <section>
          <p className="text-xs font-medium text-slate-500">创作意图</p>
          <p className="mt-1 whitespace-pre-wrap rounded border border-slate-100 bg-slate-50 p-2 text-slate-700">
            {goal}
          </p>
        </section>
        {intake?.negative_constraints_text ? (
          <section>
            <p className="text-xs font-medium text-slate-500">要避免的写法</p>
            <p className="mt-1 whitespace-pre-wrap text-slate-600">{intake.negative_constraints_text}</p>
          </section>
        ) : null}
        <p className="text-xs leading-relaxed text-slate-400">
          在对话中补充要求后，可进入大纲页生成章节结构。更多设定请用「高级编辑」。
        </p>
      </div>
      <div className="space-y-2 border-t border-slate-200 p-3">
        <button type="button" className="btn-secondary w-full text-sm" onClick={onOpenAdvanced}>
          高级编辑
        </button>
        <button
          type="button"
          className="btn-primary w-full text-sm disabled:opacity-50"
          disabled={proceeding || !goal || goal.startsWith("（尚未")}
          onClick={onProceed}
        >
          {proceeding ? "进入中…" : "进入大纲规划"}
        </button>
      </div>
    </div>
  );
}
