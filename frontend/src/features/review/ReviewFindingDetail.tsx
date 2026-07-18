import { CheckCircle2, EyeOff, Loader2, MapPin, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

import { confirmReviewApplication, undoReviewApplication } from "@/api/review";
import type { WorkspaceFinding } from "@/features/review/reviewWorkspaceApi";
import {
  applyReviewWorkspaceFinding,
  getFindingHistory,
  patchReviewWorkspaceFinding,
  recheckReviewWorkspaceFinding,
} from "@/features/review/reviewWorkspaceApi";
import { PRODUCT_DIMENSION_LABEL, type ProductDimension } from "@/features/review/reviewWorkspaceApi";

const STATUS_LABEL: Record<string, string> = {
  open: "待处理",
  applied_pending_recheck: "已应用 · 待复查",
  resolved: "已处理",
  dismissed: "已忽略",
};

const TIER_LABEL: Record<string, string> = {
  must_fix: "必须处理",
  suggest: "建议处理",
  observe: "可选观察",
  needs_verification: "待核验",
};

const DEFAULT_DATA_OPTIONS = [
  { id: "add_source", label: "补充来源", description: "绑定具体报告、机构、年份和页码" },
  { id: "mark_estimate", label: "保留为估算", description: "明确说明这是作者经验判断或非统计估计" },
  { id: "remove_number", label: "删除数字", description: "数字无法核实时，改写为不依赖精确比例的表述" },
];

const FIX_CAPABILITY_LABEL: Record<string, string> = {
  preview_apply: "可预览后一键应用",
  choice_then_apply: "需选择处理方式",
  manual_only: "需人工处理",
  observe_only: "仅观察",
};

const FIX_CAPABILITY_HELP: Record<string, string> = {
  preview_apply: "低风险、可生成修改预览。",
  choice_then_apply: "需要先选择补来源、压实、保留或删除等路径。",
  manual_only: "涉及事实、观点、结构或高风险内容，系统不自动修改。",
  observe_only: "仅作为质量提示，不建议立即修改。",
};

type Props = {
  bookId: string;
  finding: WorkspaceFinding | null;
  onUpdated: () => void;
  onJumpToSource?: (finding: WorkspaceFinding) => void;
};

export default function ReviewFindingDetail({ bookId, finding, onUpdated, onJumpToSource }: Props) {
  const [busy, setBusy] = useState<"apply" | "resolve" | "dismiss" | "recheck" | "undo" | null>(null);
  const [previewMd, setPreviewMd] = useState<string | null>(null);
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [history, setHistory] = useState<Array<{ application_id: string; apply_type: string; created_at: string | null }>>([]);

  useEffect(() => {
    if (!finding || finding.source !== "chapter") {
      setHistory([]);
      return;
    }
    void getFindingHistory(bookId, finding.id)
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [bookId, finding?.id, finding?.source]);

  if (!finding) {
    return <div className="flex h-full items-center justify-center p-8 text-sm text-slate-500">选择左侧问题查看详情与依据</div>;
  }

  const actionOptions =
    finding.action_options && finding.action_options.length > 0
      ? finding.action_options
      : finding.tier === "needs_verification" || finding.prefer_evidence_binding
        ? DEFAULT_DATA_OPTIONS
        : [];
  const evidenceItems = finding.evidence_items ?? [];

  async function handleApply(optionId?: string) {
    if (finding?.source !== "chapter") {
      toast.error("全书级建议请手动修改或标记状态");
      return;
    }
    if (optionId === "add_source") {
      toast("请到文献面板绑定来源，或在正文手动插入（来源：机构，年份）标注", { icon: "📎" });
      return;
    }
    setBusy("apply");
    try {
      const res = await applyReviewWorkspaceFinding(bookId, finding.id, {
        action_option_id: optionId,
        action_type: optionId ? "revise" : undefined,
      });
      setPreviewMd(res.result_markdown);
      setApplicationId(res.application_id);
      toast.success("已生成修改预览，确认后应用");
      onUpdated();
    } catch (e: unknown) {
      let detail = "生成修改预览失败";
      if (typeof e === "object" && e && "response" in e) {
        const data = (e as { response?: { data?: { detail?: unknown } } }).response?.data;
        if (typeof data?.detail === "string" && data.detail.trim()) detail = data.detail;
      } else if (e instanceof Error && e.message) {
        detail = e.message;
      }
      toast.error(detail);
    } finally {
      setBusy(null);
    }
  }

  async function confirmPreview() {
    if (!applicationId) return;
    setBusy("apply");
    try {
      await confirmReviewApplication(bookId, applicationId);
      setPreviewMd(null);
      setApplicationId(null);
      toast.success("已应用修改，待复查");
      onUpdated();
    } catch {
      toast.error("应用失败，请确认正文与预览一致");
    } finally {
      setBusy(null);
    }
  }

  async function handleRecheck() {
    setBusy("recheck");
    try {
      await recheckReviewWorkspaceFinding(bookId, finding!.id);
      toast.success("复查完成");
      onUpdated();
    } catch {
      toast.error("复查失败");
    } finally {
      setBusy(null);
    }
  }

  async function handleUndo() {
    const last = history[0];
    if (!last) return;
    setBusy("undo");
    try {
      await undoReviewApplication(bookId, last.application_id);
      toast.success("已撤销上次应用");
      onUpdated();
    } catch {
      toast.error("撤销失败");
    } finally {
      setBusy(null);
    }
  }

  async function patchStatus(status: string) {
    setBusy(status === "resolved" ? "resolve" : "dismiss");
    try {
      await patchReviewWorkspaceFinding(bookId, finding!.id, finding!.source, status);
      toast.success(status === "resolved" ? "已标记解决" : "已忽略");
      onUpdated();
    } catch {
      toast.error("更新状态失败");
    } finally {
      setBusy(null);
    }
  }

  const fixCapability = finding.fix_capability ?? (actionOptions.length > 0 ? "choice_then_apply" : null);
  const hasLocation =
    finding.source === "chapter" &&
    (finding.chapter_index != null ||
      finding.paragraph_index != null ||
      finding.paragraph_id ||
      finding.char_start != null ||
      finding.quote);
  const canApply =
    finding.source === "chapter" &&
    finding.locatable &&
    finding.status === "open" &&
    fixCapability !== "manual_only" &&
    fixCapability !== "observe_only";
  const canGenerateDefaultPreview = canApply && (fixCapability === "preview_apply" || (!fixCapability && actionOptions.length === 0));
  const canRecheck = finding.status === "applied_pending_recheck";

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold text-ink">{finding.title}</h3>
          <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px]">{STATUS_LABEL[finding.status] ?? finding.status}</span>
          <span className="rounded bg-amber-50 px-2 py-0.5 text-[10px] text-amber-900">
            {TIER_LABEL[finding.tier] ?? finding.tier}
          </span>
          {finding.product_dimension ? (
            <span className="rounded bg-violet-50 px-2 py-0.5 text-[10px] text-violet-800">
              {PRODUCT_DIMENSION_LABEL[finding.product_dimension as ProductDimension]}
            </span>
          ) : null}
          {fixCapability ? (
            <span className="rounded bg-indigo-50 px-2 py-0.5 text-[10px] text-indigo-800">
              {FIX_CAPABILITY_LABEL[fixCapability] ?? fixCapability}
            </span>
          ) : null}
        </div>
      </div>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5 text-sm">
        <section>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">问题</p>
          <p className="mt-1 leading-relaxed text-slate-700">{finding.title}</p>
          {finding.detail && finding.detail !== finding.title ? (
            <p className="mt-1 text-xs leading-relaxed text-slate-600">{finding.detail}</p>
          ) : null}
        </section>
        <section>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">定位</p>
          {hasLocation ? (
            <div className="mt-1 rounded border border-emerald-100 bg-emerald-50/60 px-3 py-2 text-xs text-emerald-950">
              <p>
                {finding.chapter_index != null ? `第 ${finding.chapter_index} 章` : "章节级定位"}
                {finding.chapter_title ? ` · ${finding.chapter_title}` : ""}
              </p>
              <p className="mt-0.5 text-[11px] text-emerald-800">
                {finding.paragraph_index != null ? `段落 ${finding.paragraph_index + 1}` : "段落待匹配"}
                {finding.char_start != null && finding.char_end != null ? ` · 字符 ${finding.char_start}-${finding.char_end}` : ""}
              </p>
              {onJumpToSource && finding.chapter_index != null ? (
                <button
                  type="button"
                  className="mt-2 rounded border border-emerald-200 bg-white px-2 py-1 text-[11px] font-medium text-emerald-800 hover:bg-emerald-50"
                  onClick={() => onJumpToSource(finding)}
                >
                  跳转到正文
                </button>
              ) : null}
            </div>
          ) : (
            <p className="mt-1 text-xs text-slate-400">暂未生成可跳转定位</p>
          )}
        </section>
        <section>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">原文证据</p>
          {finding.quote ? (
            <p className="mt-1 rounded border border-slate-100 bg-slate-50 p-3 text-xs italic text-slate-800">{finding.quote}</p>
          ) : (
            <p className="mt-1 text-xs text-slate-400">未定位到原文片段</p>
          )}
        </section>
        <section>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">依据来源</p>
          {finding.basis_refs.length ? (
            <ul className="mt-2 space-y-1">
              {finding.basis_refs.map((ref) => (
                <li key={ref} className="rounded border border-teal-100 bg-teal-50/60 px-2 py-1 text-xs text-teal-900">
                  {ref}
                </li>
              ))}
            </ul>
          ) : null}
          {evidenceItems.length ? (
            <div className="mt-2 space-y-2">
              {evidenceItems.map((item, index) => (
                <div key={`${item.type}-${index}`} className="rounded border border-sky-100 bg-sky-50/60 px-3 py-2 text-xs text-sky-950">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{item.label}</span>
                    {item.source ? <span className="rounded bg-white/70 px-1.5 py-0.5 text-[10px] text-sky-700">{item.source}</span> : null}
                  </div>
                  <p className="mt-1 leading-relaxed">{item.detail}</p>
                  {item.examples?.length ? (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {item.examples.slice(0, 4).map((example) => (
                        <span key={example} className="rounded bg-white/70 px-1.5 py-0.5 text-[10px] text-sky-800">
                          {example}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
          {!finding.basis_refs.length && !evidenceItems.length ? (
            <p className="mt-1 text-xs text-slate-400">暂无结构化依据来源</p>
          ) : null}
        </section>
        <section>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">影响</p>
          {finding.why_it_matters ? (
            <p className="mt-1 leading-relaxed text-slate-700">{finding.why_it_matters}</p>
          ) : (
            <p className="mt-1 text-xs text-slate-400">未单独说明影响（避免与问题描述重复）</p>
          )}
          {finding.impact_scope ? (
            <p className="mt-1 text-[11px] text-slate-500">影响范围：{finding.impact_scope}</p>
          ) : null}
        </section>
        <section>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">处理方式</p>
          {fixCapability ? (
            <div className="mt-1 rounded border border-indigo-100 bg-indigo-50/60 px-3 py-2 text-xs text-indigo-900">
              <p className="font-medium">{FIX_CAPABILITY_LABEL[fixCapability] ?? fixCapability}</p>
              <p className="mt-0.5 text-[11px]">{FIX_CAPABILITY_HELP[fixCapability] ?? ""}</p>
            </div>
          ) : null}
          {actionOptions.length > 0 ? (
            <div className="mt-2 space-y-2">
              {actionOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className="flex w-full flex-col rounded border border-slate-200 bg-white px-3 py-2 text-left hover:border-indigo-300 hover:bg-indigo-50/40 disabled:opacity-50"
                  disabled={busy != null || !canApply}
                  onClick={() => void handleApply(opt.id)}
                >
                  <span className="text-sm font-medium text-slate-800">{opt.label}</span>
                  {opt.description ? <span className="mt-0.5 text-[11px] text-slate-500">{opt.description}</span> : null}
                </button>
              ))}
              <p className="text-[11px] text-slate-400">不会自动把数字改成「相当比例」等空泛表述。</p>
            </div>
          ) : finding.suggestion ? (
            <p className="mt-1 leading-relaxed text-slate-700">{finding.suggestion}</p>
          ) : (
            <p className="mt-1 text-xs text-slate-400">暂无结构化处理选项</p>
          )}
        </section>
        {previewMd ? (
          <section>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">修改预览</p>
            <div className="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap rounded border bg-slate-50 p-3 text-xs">
              {previewMd.slice(0, 4000)}
            </div>
            <button
              type="button"
              className="btn-primary mt-2 h-8 px-3 text-xs"
              disabled={busy != null}
              onClick={() => void confirmPreview()}
            >
              确认应用
            </button>
          </section>
        ) : null}
        {history.length ? (
          <section>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">处理历史</p>
            <ul className="mt-1 space-y-1 text-[11px] text-slate-600">
              {history.map((h) => (
                <li key={h.application_id} className="rounded border border-slate-100 px-2 py-1">
                  {h.apply_type} · {h.created_at ? new Date(h.created_at).toLocaleString() : ""}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-2 border-t border-slate-200 p-4">
        {canGenerateDefaultPreview && actionOptions.length === 0 ? (
          <button
            type="button"
            className="btn-primary flex h-9 items-center gap-1.5 px-3 text-xs"
            disabled={busy != null}
            onClick={() => void handleApply()}
          >
            {busy === "apply" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MapPin className="h-3.5 w-3.5" />}
            生成修改预览
          </button>
        ) : null}
        {canRecheck ? (
          <button
            type="button"
            className="btn-primary flex h-9 items-center gap-1.5 px-3 text-xs"
            disabled={busy != null}
            onClick={() => void handleRecheck()}
          >
            {busy === "recheck" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            复查本条
          </button>
        ) : null}
        {history.length ? (
          <button
            type="button"
            className="btn-secondary flex h-9 items-center gap-1.5 px-3 text-xs"
            disabled={busy != null}
            onClick={() => void handleUndo()}
          >
            撤销应用
          </button>
        ) : null}
        <button
          type="button"
          className="btn-secondary flex h-9 items-center gap-1.5 px-3 text-xs"
          disabled={busy != null}
          onClick={() => void patchStatus("resolved")}
        >
          <CheckCircle2 className="h-3.5 w-3.5" /> 标记解决
        </button>
        <button
          type="button"
          className="btn-secondary flex h-9 items-center gap-1.5 px-3 text-xs"
          disabled={busy != null}
          onClick={() => void patchStatus("dismissed")}
        >
          <EyeOff className="h-3.5 w-3.5" /> 忽略
        </button>
      </div>
    </div>
  );
}
