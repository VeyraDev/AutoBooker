import { CheckCircle2, ChevronDown, ChevronUp, EyeOff, ExternalLink, History, Loader2, MapPin, RotateCcw, ShieldCheck, Wand2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { Link } from "react-router-dom";

import {
  confirmReviewApplication,
  dismissReviewIssue,
  getLatestReview,
  getReviewHistory,
  previewReviewIssue,
  previewReviewIssueDedupe,
  recheckReview,
  resolveReviewIssue,
} from "@/api/review";
import { runReviewWorkspace } from "@/features/review/reviewWorkspaceApi";
import { dedupeChapter } from "@/api/chapters";
import ReviewRadarChart from "@/components/editor/ReviewRadarChart";
import { cleanSuggestionText } from "@/lib/cleanSuggestion";
import type { EditorAiPreviewPayload } from "@/types/aiPreview";
import type { ChapterReviewResult, ReviewActionType, ReviewHistoryItem, ReviewIssue, ReviewIssueStatus } from "@/types/review";
import {
  REVIEW_ACTION_LABEL,
  REVIEW_CATEGORY_LABEL,
  REVIEW_DIMENSION_LABEL,
  REVIEW_SEVERITY_LABEL,
  REVIEW_STATUS_LABEL,
} from "@/types/review";

function uiStorageKey(bookId: string, chapterIndex: number) {
  return `autobooker:review-ui:${bookId}:${chapterIndex}`;
}

type Props = {
  bookId: string;
  chapterIndex: number | null;
  chapterTitle?: string;
  onApplySuggestion?: (quote: string, suggestion: string) => void;
  onAiPreviewReady?: (payload: EditorAiPreviewPayload) => boolean | void;
  onChapterMarkdownReplace?: (markdown: string) => void;
  chapterContext?: string;
  reviewRunResult?: Record<string, unknown>;
};

const SEVERITY_CLASS: Record<string, string> = {
  high: "bg-red-50 text-red-800 border-red-200",
  medium: "bg-amber-50 text-amber-900 border-amber-200",
  low: "bg-slate-50 text-slate-700 border-slate-200",
};

const STATUS_OPTIONS: Array<ReviewIssueStatus | "all"> = ["open", "resolved", "dismissed", "stale", "failed", "all"];

function isAiSignatureIssue(issue: ReviewIssue): boolean {
  return issue.dimension === "ai_signature" || Boolean(issue.detector?.startsWith("ai_detect"));
}

export default function ReviewPanel({
  bookId,
  chapterIndex,
  chapterTitle,
  onAiPreviewReady,
  onChapterMarkdownReplace,
  reviewRunResult,
}: Props) {
  const [reviewing, setReviewing] = useState(false);
  const [loadingLatest, setLoadingLatest] = useState(false);
  const [dedupeBusy, setDedupeBusy] = useState(false);
  const [dedupePreview, setDedupePreview] = useState<{ original: string; suggestion: string } | null>(null);
  const [report, setReport] = useState<ChapterReviewResult | null>(null);
  const [activeDimension, setActiveDimension] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ReviewIssueStatus | "all">("open");
  const [severityFilter, setSeverityFilter] = useState<"all" | "high" | "medium" | "low">("all");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyRows, setHistoryRows] = useState<ReviewHistoryItem[]>([]);
  const [radarOpen, setRadarOpen] = useState(false);
  const [exprOpen, setExprOpen] = useState(false);

  useEffect(() => {
    if (chapterIndex == null) {
      setReport(null);
      setDedupePreview(null);
      return;
    }
    try {
      const raw = sessionStorage.getItem(uiStorageKey(bookId, chapterIndex));
      if (raw) {
        const ui = JSON.parse(raw) as { activeDimension?: string | null; statusFilter?: ReviewIssueStatus | "all" };
        setActiveDimension(ui.activeDimension ?? null);
        setStatusFilter(ui.statusFilter ?? "open");
      }
    } catch {
      /* ignore */
    }
    setLoadingLatest(true);
    getLatestReview(bookId, chapterIndex)
      .then((res) => setReport(res))
      .catch(() => toast.error("读取审校报告失败"))
      .finally(() => setLoadingLatest(false));
  }, [bookId, chapterIndex]);

  useEffect(() => {
    if (!reviewRunResult) return;
    toast.success(String(reviewRunResult.message ?? "审校已完成，请在工作台查看详情"));
    if (chapterIndex != null) {
      setLoadingLatest(true);
      getLatestReview(bookId, chapterIndex)
        .then((res) => setReport(res))
        .catch(() => undefined)
        .finally(() => setLoadingLatest(false));
    }
  }, [reviewRunResult, bookId, chapterIndex]);

  useEffect(() => {
    if (chapterIndex == null) return;
    try {
      sessionStorage.setItem(
        uiStorageKey(bookId, chapterIndex),
        JSON.stringify({ activeDimension, statusFilter }),
      );
    } catch {
      /* quota */
    }
  }, [activeDimension, statusFilter, bookId, chapterIndex]);

  const visibleIssues = useMemo(() => {
    const issues = report?.issues ?? [];
    return issues.filter((issue) => {
      const status = issue.stale ? "stale" : issue.status ?? "open";
      if (issue.severity !== "high") return false;
      if (activeDimension && issue.dimension !== activeDimension) return false;
      if (statusFilter !== "all" && status !== statusFilter) return false;
      if (severityFilter !== "all" && issue.severity !== severityFilter) return false;
      return true;
    });
  }, [report, activeDimension, statusFilter, severityFilter]);

  const aiOpenIssueCount = useMemo(() => {
    return (report?.issues ?? []).filter((issue) => {
      const status = issue.stale ? "stale" : issue.status ?? "open";
      return isAiSignatureIssue(issue) && (status === "open" || status === "stale");
    }).length;
  }, [report]);

  const refreshLatest = useCallback(async () => {
    if (chapterIndex == null) return;
    const latest = await getLatestReview(bookId, chapterIndex);
    setReport(latest);
  }, [bookId, chapterIndex]);

  async function runReview() {
    if (chapterIndex == null) {
      toast.error("请先选择章节");
      return;
    }
    setReviewing(true);
    try {
      await runReviewWorkspace(bookId, { scope: "chapter", chapter_index: chapterIndex });
      const res = await getLatestReview(bookId, chapterIndex);
      setReport(res);
      setActiveDimension(null);
      toast.success("审校完成");
    } catch {
      toast.error("审校失败，请稍后重试");
    } finally {
      setReviewing(false);
    }
  }

  async function runRecheck() {
    if (!report?.review_id) {
      await runReview();
      return;
    }
    setReviewing(true);
    try {
      const res = await recheckReview(bookId, report.review_id);
      setReport(res);
      toast.success("已重新审校");
    } catch {
      toast.error("重新审校失败");
    } finally {
      setReviewing(false);
    }
  }

  async function loadHistory() {
    if (chapterIndex == null) return;
    setHistoryOpen((v) => !v);
    if (historyRows.length) return;
    try {
      setHistoryRows(await getReviewHistory(bookId, chapterIndex));
    } catch {
      toast.error("读取审校历史失败");
    }
  }

  async function runDedupeChapter() {
    if (chapterIndex == null) {
      toast.error("请先选择章节");
      return;
    }
    setDedupeBusy(true);
    setDedupePreview(null);
    try {
      const { text: out, original_text: original } = await dedupeChapter(bookId, chapterIndex);
      const cleaned = cleanSuggestionText(out);
      if (!cleaned.trim()) {
        toast.error("未生成有效修改，请重试");
        return;
      }
      setDedupePreview({ original: original.trim(), suggestion: cleaned });
      toast.success("已生成预览，请确认后应用");
    } catch {
      toast.error("改写失败，请稍后重试");
    } finally {
      setDedupeBusy(false);
    }
  }

  function applyDedupePreview() {
    if (!dedupePreview) return;
    if (onChapterMarkdownReplace) {
      onChapterMarkdownReplace(dedupePreview.suggestion);
      setDedupePreview(null);
      toast.success("已应用改写，请检查后保存");
    } else {
      toast.error("未能应用修改，请重试");
    }
  }

  function scoreColor(score: number) {
    if (score >= 85) return "text-emerald-600";
    if (score >= 70) return "text-amber-700";
    return "text-red-600";
  }

  return (
    <div className="space-y-5 text-sm">
      <section>
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">本章必改项</p>
            {chapterTitle ? <p className="mt-1 text-xs font-medium text-ink">{chapterTitle}</p> : null}
          </div>
          {loadingLatest ? <Loader2 className="h-4 w-4 animate-spin text-slate-400" /> : null}
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
          快捷查看当前章必改问题；完整审校请在工作台处理。
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            className="btn-secondary flex h-9 items-center justify-center gap-2 text-xs"
            disabled={reviewing || chapterIndex == null}
            onClick={() => void runReview()}
          >
            {reviewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            {reviewing ? "审校中..." : "开始审校"}
          </button>
          <button
            type="button"
            className="btn-secondary flex h-9 items-center justify-center gap-2 text-xs"
            disabled={reviewing || chapterIndex == null}
            onClick={() => void runRecheck()}
          >
            <RotateCcw className="h-4 w-4" />
            重新审校
          </button>
        </div>
      </section>

      {report ? (
        <section className="space-y-3 border-t border-slate-100 pt-3">
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-1">
              <span className="text-xs text-slate-500">质量评分</span>
              {report.created_at ? <p className="text-[10px] text-slate-400">{new Date(report.created_at).toLocaleString()}</p> : null}
              {report.is_stale ? (
                <p className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-800">
                  当前正文与审校快照不一致，旧建议应用前需要重新定位。
                </p>
              ) : null}
            </div>
            <span className={`text-lg font-semibold ${scoreColor(report.score)}`}>{report.score}</span>
          </div>
          <button
            type="button"
            className="flex w-full items-center justify-center gap-1 text-[10px] text-slate-500 hover:text-slate-800"
            onClick={() => setRadarOpen((v) => !v)}
          >
            {radarOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {radarOpen ? "收起质量雷达" : "展开质量雷达"}
          </button>
          {radarOpen ? (
            <ReviewRadarChart
              dimensions={report.dimension_rows?.length ? report.dimension_rows : report.dimensions ?? {}}
              activeKey={activeDimension}
              onSelect={setActiveDimension}
            />
          ) : null}
          <p className="text-xs leading-relaxed text-slate-600">{report.summary}</p>
          <div className="flex flex-wrap items-center gap-1.5">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                type="button"
                className={`rounded border px-2 py-1 text-[10px] ${
                  statusFilter === s ? "border-teal-300 bg-teal-50 text-teal-900" : "border-slate-200 bg-white text-slate-600"
                }`}
                onClick={() => setStatusFilter(s)}
              >
                {s === "all" ? "全部" : REVIEW_STATUS_LABEL[s]}
              </button>
            ))}
            {(["all", "high", "medium", "low"] as const).map((s) => (
              <button
                key={s}
                type="button"
                className={`rounded border px-2 py-1 text-[10px] ${
                  severityFilter === s ? "border-slate-400 bg-slate-100 text-slate-900" : "border-slate-200 bg-white text-slate-600"
                }`}
                onClick={() => setSeverityFilter(s)}
              >
                {s === "all" ? "全部级别" : REVIEW_SEVERITY_LABEL[s]}
              </button>
            ))}
            <button type="button" className="ml-auto flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-800" onClick={() => void loadHistory()}>
              <History className="h-3.5 w-3.5" />
              历史
            </button>
          </div>

          {historyOpen ? (
            <div className="max-h-36 space-y-1 overflow-y-auto rounded border border-slate-200 bg-slate-50 p-2 text-[10px]">
              {historyRows.length ? historyRows.map((row) => (
                <div key={row.review_id} className="flex items-center justify-between gap-2 rounded bg-white px-2 py-1">
                  <span className="truncate">{new Date(row.created_at).toLocaleString()}</span>
                  <span className={row.is_stale ? "text-amber-700" : "text-slate-500"}>{row.is_stale ? "旧版本" : row.status}</span>
                  <span className="font-semibold">{row.score}</span>
                </div>
              )) : <p className="text-slate-500">暂无历史审校</p>}
            </div>
          ) : null}

          {visibleIssues.length === 0 ? (
            <p className="flex items-center gap-1 text-xs text-emerald-700">
              <ShieldCheck className="h-3.5 w-3.5" />
              当前筛选下没有问题
            </p>
          ) : (
            <ul className="max-h-[360px] space-y-2 overflow-y-auto pr-1">
              {visibleIssues.map((issue) => (
                <IssueCard
                  key={issue.id}
                  bookId={bookId}
                  issue={issue}
                  onRefresh={() => void refreshLatest()}
                  onReportChange={setReport}
                  onAiPreviewReady={onAiPreviewReady}
                />
              ))}
            </ul>
          )}
        </section>
      ) : (
        <p className="rounded border border-slate-100 bg-slate-50 p-3 text-xs text-slate-500">
          暂无审校报告。点击“开始审校”会生成本章审校报告。
        </p>
      )}
      <Link
        to={`/app/books/${bookId}/review`}
        className="flex items-center justify-center gap-1 rounded border border-teal-200 bg-teal-50 px-3 py-2 text-xs font-medium text-teal-900 hover:bg-teal-100"
      >
        <ExternalLink className="h-3.5 w-3.5" />
        在工作台查看全书审校
      </Link>

      <section className="border-t border-slate-100 pt-3">
        <button
          type="button"
          className="flex w-full items-center justify-center gap-1 text-[10px] text-slate-500 hover:text-slate-800"
          onClick={() => setExprOpen((v) => !v)}
        >
          {exprOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {exprOpen ? "收起表达优化" : "展开表达优化（非审校）"}
        </button>
        {exprOpen ? (
          <div className="mt-3 space-y-2">
            {aiOpenIssueCount > 0 ? (
              <p className="rounded border border-teal-100 bg-teal-50 px-2 py-1 text-[11px] text-teal-800">
                审校已定位 {aiOpenIssueCount} 个表达生硬片段，可逐条优化。
              </p>
            ) : null}
            <button
              type="button"
              className="btn-secondary flex h-9 w-full items-center justify-center gap-2 text-xs"
              disabled={dedupeBusy || chapterIndex == null}
              onClick={() => void runDedupeChapter()}
            >
              {dedupeBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
              优化整章表达
            </button>
            {dedupePreview ? (
              <div className="space-y-2 rounded-lg border border-teal-200 bg-teal-50/60 p-3">
                <p className="text-xs font-medium text-teal-900">改写预览</p>
                <div className="max-h-40 overflow-y-auto rounded border border-teal-100 bg-white/80 p-2 text-[10px] whitespace-pre-wrap">
                  {dedupePreview.suggestion.slice(0, 2400)}
                </div>
                <div className="flex gap-2">
                  <button type="button" className="btn-primary h-8 flex-1 text-[11px]" onClick={applyDedupePreview}>应用替换</button>
                  <button type="button" className="btn-secondary h-8 flex-1 text-[11px]" onClick={() => setDedupePreview(null)}>放弃</button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function IssueCard({
  bookId,
  issue,
  onRefresh,
  onReportChange,
  onAiPreviewReady,
}: {
  bookId: string;
  issue: ReviewIssue;
  onRefresh: () => void;
  onReportChange: (report: ChapterReviewResult | null) => void;
  onAiPreviewReady?: (payload: EditorAiPreviewPayload) => boolean | void;
}) {
  const sev = issue.severity || "medium";
  const status = issue.stale ? "stale" : issue.status ?? "open";
  const action: ReviewActionType = issue.action ?? issue.action_type ?? "revise";
  const aiSignature = isAiSignatureIssue(issue);
  const [busy, setBusy] = useState<"preview" | "dismiss" | "resolve" | null>(null);

  async function tryPreview() {
    setBusy("preview");
    try {
      const res = await (aiSignature ? previewReviewIssueDedupe(bookId, issue.id) : previewReviewIssue(bookId, issue.id));
      const kind = res.preview_kind === "insert" ? "insert" : "replace";
      const suggestion = res.preview_kind === "delete" ? "" : cleanSuggestionText(res.result_text);
      const ok = onAiPreviewReady?.({
        quote: res.quote || issue.quote,
        suggestion,
        kind,
        char_offset: res.char_start ?? issue.char_start ?? issue.char_offset ?? undefined,
        char_start: res.char_start,
        char_end: res.char_end,
        paragraph_index: res.paragraph_index ?? issue.paragraph_index ?? undefined,
        paragraph_id: res.paragraph_id ?? issue.paragraph_id ?? undefined,
        locator_confidence: res.locator_confidence,
        application_id: res.application_id,
        issue_id: issue.id,
        onAccepted: async () => {
          if (res.application_id) {
            await confirmReviewApplication(bookId, res.application_id);
            await onRefresh();
          }
        },
      });
      if (!ok) {
        toast.error("未在正文中定位到对应片段，请核对原文或手动选中后重试");
        return;
      }
      const report = res.warning?.dedupe_report as { before_ai_risk?: number; after_ai_risk?: number } | undefined;
      if (aiSignature && report?.before_ai_risk != null && report?.after_ai_risk != null) {
        toast.success("已生成所选片段的优化预览");
      } else {
        toast.success(res.preview_required ? "已生成预览，确认后应用" : "已定位并生成预览");
      }
      if (res.warning?.message) toast.error(String(res.warning.message));
    } catch {
      toast.error(aiSignature ? "未能生成所选片段的优化预览" : "生成修改预览失败");
    } finally {
      setBusy(null);
    }
  }

  async function dismissIssue() {
    setBusy("dismiss");
    try {
      onReportChange(await dismissReviewIssue(bookId, issue.id));
      toast.success("已忽略");
    } catch {
      toast.error("忽略失败");
    } finally {
      setBusy(null);
    }
  }

  async function resolveIssue() {
    setBusy("resolve");
    try {
      onReportChange(await resolveReviewIssue(bookId, issue.id));
      toast.success("已标记解决");
    } catch {
      toast.error("标记失败");
    } finally {
      setBusy(null);
    }
  }

  const canPreview = status === "open" || status === "stale";
  const dimensionLabel = issue.dimension ? REVIEW_DIMENSION_LABEL[issue.dimension as keyof typeof REVIEW_DIMENSION_LABEL] ?? issue.dimension : REVIEW_CATEGORY_LABEL[issue.category];

  return (
    <li className={`rounded-lg border p-2.5 text-xs ${SEVERITY_CLASS[sev] ?? SEVERITY_CLASS.medium}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-semibold">{issue.title}</span>
        <span className="rounded bg-white/60 px-1 py-0.5 text-[10px]">{REVIEW_SEVERITY_LABEL[issue.severity]}</span>
        <span className="rounded bg-white/60 px-1 py-0.5 text-[10px]">{dimensionLabel}</span>
        <span className="rounded bg-teal-100 px-1 py-0.5 text-[10px] text-teal-800">{REVIEW_ACTION_LABEL[action]}</span>
        <span className="rounded bg-white/60 px-1 py-0.5 text-[10px]">{REVIEW_STATUS_LABEL[status]}</span>
        {issue.penalty ? <span className="rounded bg-white/60 px-1 py-0.5 text-[10px]">-{issue.penalty}</span> : null}
      </div>
      <p className="mt-1.5 leading-relaxed opacity-90">{issue.explanation || issue.detail}</p>
      {issue.quote ? <p className="mt-1.5 rounded bg-white/50 px-2 py-1 text-[10px] italic leading-relaxed">「{issue.quote}」</p> : null}
      {issue.replacement_text || issue.suggestion ? (
        <p className="mt-1.5 text-[10px] leading-relaxed">
          <span className="font-medium">建议：</span>
          {issue.replacement_text || issue.suggestion}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-3">
        {canPreview ? (
          <button type="button" className="flex items-center gap-1 text-[10px] font-medium text-teal-800 hover:underline disabled:opacity-50" disabled={busy != null} onClick={() => void tryPreview()}>
            {busy === "preview" ? <Loader2 className="h-3 w-3 animate-spin" /> : aiSignature ? <Wand2 className="h-3 w-3" /> : <MapPin className="h-3 w-3" />}
            {aiSignature ? "优化所选片段" : "定位并预览"}
          </button>
        ) : null}
        {status === "open" ? (
          <>
            <button type="button" className="flex items-center gap-1 text-[10px] font-medium text-slate-700 hover:underline disabled:opacity-50" disabled={busy != null} onClick={() => void resolveIssue()}>
              {busy === "resolve" ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
              标记解决
            </button>
            <button type="button" className="flex items-center gap-1 text-[10px] font-medium text-slate-700 hover:underline disabled:opacity-50" disabled={busy != null} onClick={() => void dismissIssue()}>
              {busy === "dismiss" ? <Loader2 className="h-3 w-3 animate-spin" /> : <EyeOff className="h-3 w-3" />}
              忽略
            </button>
          </>
        ) : null}
      </div>
    </li>
  );
}
