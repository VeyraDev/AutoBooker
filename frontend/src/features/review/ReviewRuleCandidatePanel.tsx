import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, History, Loader2, RotateCcw, ShieldCheck, XCircle } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";

import {
  decideReviewRuleCandidate,
  listConfirmedReviewRules,
  listReviewRuleVersions,
  listReviewRuleCandidates,
  PRODUCT_DIMENSION_LABEL,
  restoreReviewRuleVersion,
  type ProductDimension,
  type ReviewRuleCandidate,
  type ReviewRuleDecision,
} from "@/features/review/reviewWorkspaceApi";

type Props = {
  bookId: string;
};

const RECOMMENDATION_LABEL: Record<string, string> = {
  promote: "建议升权",
  demote: "建议降噪",
};

const RULE_STATUS_LABEL: Record<string, string> = {
  active: "当前",
  archived: "历史",
  rejected: "已驳回",
};

const GATE_STATUS_LABEL: Record<string, string> = {
  passed: "门禁已通过",
  failed: "门禁未通过",
};

export default function ReviewRuleCandidatePanel({ bookId }: Props) {
  const qc = useQueryClient();
  const [showHistory, setShowHistory] = useState(false);

  const candidatesQ = useQuery({
    queryKey: ["reviewRuleCandidates", bookId],
    queryFn: () => listReviewRuleCandidates(bookId),
    enabled: !!bookId,
  });

  const rulesQ = useQuery({
    queryKey: ["confirmedReviewRules", bookId],
    queryFn: () => listConfirmedReviewRules(bookId),
    enabled: !!bookId,
  });

  const historyQ = useQuery({
    queryKey: ["reviewRuleVersions", bookId],
    queryFn: () => listReviewRuleVersions(bookId),
    enabled: !!bookId && showHistory,
  });

  const decisionMut = useMutation({
    mutationFn: (payload: { candidate: ReviewRuleCandidate; decision: "active" | "rejected" }) =>
      decideReviewRuleCandidate(bookId, payload.candidate.id, {
        decision: payload.decision,
        decision_note: payload.decision === "active" ? "在审校工作台确认为项目规则" : "在审校工作台驳回候选规则",
        rule_text: payload.decision === "active" ? payload.candidate.reason : "",
      }),
    onSuccess: (_, payload) => {
      toast.success(payload.decision === "active" ? "已确认为项目规则" : "已驳回候选");
      void qc.invalidateQueries({ queryKey: ["reviewRuleCandidates", bookId] });
      void qc.invalidateQueries({ queryKey: ["confirmedReviewRules", bookId] });
    },
    onError: () => toast.error("处理规则候选失败"),
  });

  const restoreMut = useMutation({
    mutationFn: (rule: ReviewRuleDecision) =>
      restoreReviewRuleVersion(bookId, rule.id, {
        decision_note: `从审校工作台恢复 v${rule.version}`,
      }),
    onSuccess: () => {
      toast.success("已恢复为新的项目规则版本");
      void qc.invalidateQueries({ queryKey: ["reviewRuleCandidates", bookId] });
      void qc.invalidateQueries({ queryKey: ["confirmedReviewRules", bookId] });
      void qc.invalidateQueries({ queryKey: ["reviewRuleVersions", bookId] });
    },
    onError: () => toast.error("恢复规则版本失败"),
  });

  const candidates = candidatesQ.data ?? [];
  const activeRules = rulesQ.data ?? [];
  const activeByCandidate = new Map(activeRules.map((rule) => [rule.candidate_id, rule]));
  const history = historyQ.data ?? [];
  const visibleCandidates = candidates.slice(0, 3);

  if (candidatesQ.isLoading || rulesQ.isLoading) {
    return (
      <div className="border-b border-slate-200 px-4 py-3 text-xs text-slate-500">
        <span className="inline-flex items-center gap-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          加载项目规则…
        </span>
      </div>
    );
  }

  if (!visibleCandidates.length && !activeRules.length) {
    return (
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-700">
          <ShieldCheck className="h-4 w-4 text-teal-700" />
          项目规则
        </div>
        <p className="mt-1 text-[11px] text-slate-500">暂无可确认的规则候选。</p>
      </div>
    );
  }

  return (
    <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-teal-700" />
          <div>
            <h3 className="text-xs font-semibold text-slate-900">项目规则</h3>
            <p className="text-[11px] text-slate-500">
              已确认 {activeRules.length} 条，待确认 {candidates.length} 条
            </p>
          </div>
        </div>
        {activeRules.length ? (
          <button
            type="button"
            className="inline-flex h-7 items-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-[11px] text-slate-700 hover:bg-slate-50"
            onClick={() => setShowHistory((v) => !v)}
          >
            <History className="h-3.5 w-3.5" />
            版本历史
          </button>
        ) : null}
      </div>

      {activeRules.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {activeRules.slice(0, 3).map((rule) => (
            <span key={rule.id} className="rounded-md border border-teal-100 bg-white px-2 py-1 text-[10px] text-teal-900">
              v{rule.version} {dimensionLabel(rule.product_dimension)} / {rule.issue_type}
              {gateStatus(rule) ? <span className="ml-1 text-slate-500">· {gateStatus(rule)}</span> : null}
            </span>
          ))}
        </div>
      ) : null}

      {visibleCandidates.length ? (
        <ul className="mt-3 space-y-2">
          {visibleCandidates.map((candidate) => (
            <li key={candidate.id} className="rounded-md border border-slate-200 bg-white p-2.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-700">
                  {RECOMMENDATION_LABEL[candidate.recommendation] ?? candidate.recommendation}
                </span>
                <span className="text-[11px] font-medium text-slate-900">
                  {dimensionLabel(candidate.product_dimension)} / {candidate.issue_type}
                </span>
                {candidate.fix_capability ? (
                  <span className="rounded-md bg-indigo-50 px-1.5 py-0.5 text-[10px] text-indigo-800">
                    {candidate.fix_capability}
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-[11px] leading-5 text-slate-600">{candidate.reason}</p>
              <p className="mt-1 text-[10px] text-slate-500">
                采纳 {candidate.accepted}，驳回 {candidate.dismissed}，打开 {candidate.open}
              </p>
              {candidate.examples.length ? (
                <p className="mt-1 line-clamp-1 text-[10px] text-slate-500">例：{candidate.examples.join("；")}</p>
              ) : null}
              <div className="mt-2 flex justify-end gap-1.5">
                <button
                  type="button"
                  className="inline-flex h-7 items-center gap-1 rounded-md border border-slate-200 px-2 text-[11px] text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                  disabled={decisionMut.isPending}
                  onClick={() => decisionMut.mutate({ candidate, decision: "rejected" })}
                >
                  <XCircle className="h-3.5 w-3.5" />
                  驳回候选
                </button>
                <button
                  type="button"
                  className="inline-flex h-7 items-center gap-1 rounded-md border border-teal-200 bg-teal-50 px-2 text-[11px] font-medium text-teal-900 hover:bg-teal-100 disabled:opacity-50"
                  disabled={decisionMut.isPending}
                  onClick={() => decisionMut.mutate({ candidate, decision: "active" })}
                >
                  {decisionMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  确认为项目规则
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {showHistory ? (
        <div className="mt-3 border-t border-slate-200 pt-3">
          {historyQ.isLoading ? (
            <p className="inline-flex items-center gap-2 text-[11px] text-slate-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              加载版本…
            </p>
          ) : history.length ? (
            <ul className="space-y-2">
              {history.map((rule) => (
                <RuleVersionItem
                  key={rule.id}
                  rule={rule}
                  activeRule={activeByCandidate.get(rule.candidate_id) ?? null}
                  restoring={restoreMut.isPending}
                  onRestore={() => restoreMut.mutate(rule)}
                />
              ))}
            </ul>
          ) : (
            <p className="text-[11px] text-slate-500">暂无版本记录。</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

function dimensionLabel(value: string) {
  return PRODUCT_DIMENSION_LABEL[value as ProductDimension] ?? value;
}

function gateStatus(rule: ReviewRuleDecision) {
  const gate = rule.source_stats?.regression_gate;
  if (!gate || typeof gate !== "object") return "";
  const status = "status" in gate ? String(gate.status || "") : "";
  const coverage = "coverage_status" in gate ? String(gate.coverage_status || "") : "";
  const label = GATE_STATUS_LABEL[status] ?? "";
  if (!label) return coverage === "none" ? "需补覆盖" : "";
  return coverage === "none" ? `${label}/需补覆盖` : label;
}

function RuleVersionItem({
  rule,
  activeRule,
  restoring,
  onRestore,
}: {
  rule: ReviewRuleDecision;
  activeRule: ReviewRuleDecision | null;
  restoring: boolean;
  onRestore: () => void;
}) {
  const canRestore = rule.status !== "active" && rule.rule_text.trim().length > 0;
  const hasDifferentActive = !!activeRule && activeRule.rule_text !== rule.rule_text;

  return (
    <li className="rounded-md border border-slate-200 bg-white p-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-700">v{rule.version}</span>
            <span className="rounded-md bg-teal-50 px-1.5 py-0.5 text-[10px] text-teal-800">
              {RULE_STATUS_LABEL[rule.status] ?? rule.status}
            </span>
            {gateStatus(rule) ? (
              <span className="rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-800">
                {gateStatus(rule)}
              </span>
            ) : null}
            <span className="text-[11px] font-medium text-slate-900">
              {dimensionLabel(rule.product_dimension)} / {rule.issue_type}
            </span>
          </div>
          <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-slate-600">{rule.rule_text || "无规则文本"}</p>
        </div>
        {canRestore ? (
          <button
            type="button"
            className="inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-teal-200 bg-teal-50 px-2 text-[11px] font-medium text-teal-900 hover:bg-teal-100 disabled:opacity-50"
            disabled={restoring}
            onClick={onRestore}
          >
            {restoring ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            恢复此版本
          </button>
        ) : null}
      </div>
      {hasDifferentActive ? (
        <div className="mt-2 space-y-1 rounded-md bg-slate-50 p-2 text-[10px] leading-4 text-slate-600">
          <p>
            <span className="font-medium text-slate-700">当前：</span>
            {activeRule?.rule_text}
          </p>
          <p>
            <span className="font-medium text-slate-700">此版：</span>
            {rule.rule_text}
          </p>
        </div>
      ) : null}
    </li>
  );
}
