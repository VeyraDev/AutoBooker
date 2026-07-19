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

type Props = {
  bookId: string;
  finding: WorkspaceFinding | null;
  onUpdated: () => void;
};

export default function ReviewFindingDetail({ bookId, finding, onUpdated }: Props) {
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

  async function handleApply() {
    if (finding?.source !== "chapter") {
      toast.error("全书级建议请手动修改或标记状态");
      return;
    }
    setBusy("apply");
    try {
      const res = await applyReviewWorkspaceFinding(bookId, finding.id);
      setPreviewMd(res.result_markdown);
      setApplicationId(res.application_id);
      toast.success("已生成修改预览，确认后应用");
      onUpdated();
    } catch {
      toast.error("生成修改预览失败");
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

  const canApply = finding.source === "chapter" && finding.locatable && finding.status === "open";
  const canRecheck = finding.status === "applied_pending_recheck";

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold text-ink">{finding.title}</h3>
          <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px]">{STATUS_LABEL[finding.status] ?? finding.status}</span>
          {finding.product_dimension ? (
            <span className="rounded bg-violet-50 px-2 py-0.5 text-[10px] text-violet-800">
              {PRODUCT_DIMENSION_LABEL[finding.product_dimension as ProductDimension]}
            </span>
          ) : null}
        </div>
      </div>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5 text-sm">
        <section>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">问题是什么</p>
          <p className="mt-1 leading-relaxed text-slate-700">{finding.detail || finding.title}</p>
        </section>
        <section>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">为什么成立</p>
          <p className="mt-1 leading-relaxed text-slate-700">{finding.why_it_matters || finding.detail}</p>
        </section>
        {finding.quote ? (
          <section>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">原文</p>
            <p className="mt-1 rounded border border-slate-100 bg-slate-50 p-3 text-xs italic">{finding.quote}</p>
          </section>
        ) : null}
        {finding.impact_scope ? (
          <section>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">影响范围</p>
            <p className="mt-1 text-xs text-slate-700">{finding.impact_scope}</p>
          </section>
        ) : null}
        {finding.basis_refs.length ? (
          <section>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">依据来源</p>
            <ul className="mt-1 space-y-1">
              {finding.basis_refs.map((ref) => (
                <li key={ref} className="rounded border border-teal-100 bg-teal-50/60 px-2 py-1 text-xs text-teal-900">{ref}</li>
              ))}
            </ul>
          </section>
        ) : null}
        {finding.suggestion ? (
          <section>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">建议操作</p>
            <p className="mt-1 leading-relaxed text-slate-700">{finding.suggestion}</p>
          </section>
        ) : null}
        {previewMd ? (
          <section>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">修改预览</p>
            <div className="mt-1 max-h-48 overflow-y-auto rounded border bg-slate-50 p-3 text-xs whitespace-pre-wrap">{previewMd.slice(0, 4000)}</div>
            <button type="button" className="btn-primary mt-2 h-8 px-3 text-xs" disabled={busy != null} onClick={() => void confirmPreview()}>确认应用</button>
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
        {canApply ? (
          <button type="button" className="btn-primary flex h-9 items-center gap-1.5 px-3 text-xs" disabled={busy != null} onClick={() => void handleApply()}>
            {busy === "apply" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MapPin className="h-3.5 w-3.5" />}
            生成修改预览
          </button>
        ) : null}
        {canRecheck ? (
          <button type="button" className="btn-primary flex h-9 items-center gap-1.5 px-3 text-xs" disabled={busy != null} onClick={() => void handleRecheck()}>
            {busy === "recheck" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            复查本条
          </button>
        ) : null}
        {history.length ? (
          <button type="button" className="btn-secondary flex h-9 items-center gap-1.5 px-3 text-xs" disabled={busy != null} onClick={() => void handleUndo()}>
            撤销应用
          </button>
        ) : null}
        <button type="button" className="btn-secondary flex h-9 items-center gap-1.5 px-3 text-xs" disabled={busy != null} onClick={() => void patchStatus("resolved")}>
          <CheckCircle2 className="h-3.5 w-3.5" /> 标记解决
        </button>
        <button type="button" className="btn-secondary flex h-9 items-center gap-1.5 px-3 text-xs" disabled={busy != null} onClick={() => void patchStatus("dismissed")}>
          <EyeOff className="h-3.5 w-3.5" /> 忽略
        </button>
      </div>
    </div>
  );
}
