import { Loader2, ShieldCheck, Wand2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";

import { applyReviewIssue, reviewChapter } from "@/api/review";
import { editChapterSelection, type SelectionEditMode } from "@/api/chapters";
import { cleanSuggestionText } from "@/lib/cleanSuggestion";
import type { EditorAiPreviewPayload } from "@/types/aiPreview";
import type {
  ChapterReviewResult,
  CitationLintIssue,
  ReviewActionType,
  ReviewIssue,
} from "@/types/review";
import { REVIEW_ACTION_LABEL, REVIEW_CATEGORY_LABEL, REVIEW_SEVERITY_LABEL } from "@/types/review";

function reviewStorageKey(bookId: string, chapterIndex: number) {
  return `autobooker:review:${bookId}:${chapterIndex}`;
}

type Props = {
  bookId: string;
  chapterIndex: number | null;
  chapterTitle?: string;
  /** 编辑器当前选区纯文本 */
  selectionText?: string;
  onApplySuggestion?: (quote: string, suggestion: string) => void;
  onAiPreviewReady?: (payload: EditorAiPreviewPayload) => boolean | void;
  chapterContext?: string;
};

const SEVERITY_CLASS: Record<string, string> = {
  high: "bg-red-50 text-red-800 border-red-200",
  medium: "bg-amber-50 text-amber-900 border-amber-200",
  low: "bg-slate-50 text-slate-700 border-slate-200",
};

export default function ReviewPanel({
  bookId,
  chapterIndex,
  chapterTitle,
  selectionText = "",
  onApplySuggestion,
  onAiPreviewReady,
  chapterContext = "",
}: Props) {
  const [reviewing, setReviewing] = useState(false);
  const [dedupeBusy, setDedupeBusy] = useState(false);
  const [report, setReport] = useState<ChapterReviewResult | null>(null);

  useEffect(() => {
    if (chapterIndex == null) {
      setReport(null);
      return;
    }
    try {
      const raw = sessionStorage.getItem(reviewStorageKey(bookId, chapterIndex));
      if (raw) setReport(JSON.parse(raw) as ChapterReviewResult);
      else setReport(null);
    } catch {
      setReport(null);
    }
  }, [bookId, chapterIndex]);

  const persistReport = useCallback(
    (r: ChapterReviewResult | null) => {
      if (chapterIndex == null) return;
      const key = reviewStorageKey(bookId, chapterIndex);
      if (!r) {
        sessionStorage.removeItem(key);
        return;
      }
      try {
        sessionStorage.setItem(key, JSON.stringify(r));
      } catch {
        /* quota */
      }
    },
    [bookId, chapterIndex],
  );

  async function runReview() {
    if (chapterIndex == null) {
      toast.error("请先选择章节");
      return;
    }
    setReviewing(true);
    try {
      const res = await reviewChapter(bookId, chapterIndex);
      setReport(res);
      persistReport(res);
      toast.success("审校完成");
    } catch {
      toast.error("审校失败，请稍后重试");
    } finally {
      setReviewing(false);
    }
  }

  async function runDedupeOnSelection() {
    const text = selectionText.trim();
    if (!text) {
      toast.error("请先在正文中选中需要降重的段落");
      return;
    }
    if (chapterIndex == null) {
      toast.error("请先选择章节");
      return;
    }
    setDedupeBusy(true);
    try {
      const { text: out } = await editChapterSelection(bookId, chapterIndex, {
        mode: "dedupe" as SelectionEditMode,
        text,
      });
      const cleaned = cleanSuggestionText(out);
      if (
        onAiPreviewReady?.({
          quote: text,
          suggestion: cleaned,
          kind: "replace",
        })
      ) {
        toast.success("已生成预览，请确认后应用");
      } else {
        onApplySuggestion?.(text, cleaned);
        toast.success("已生成降重文本，请确认后保留");
      }
    } catch {
      toast.error("降重失败");
    } finally {
      setDedupeBusy(false);
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
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">AI 降重</p>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
          在正文选中一段文字，点击下方按钮进行语义降重（保留原意，改写表述）。
        </p>
        <button
          type="button"
          className="btn-primary mt-3 flex h-9 w-full items-center justify-center gap-2 text-xs"
          disabled={dedupeBusy || !selectionText.trim()}
          onClick={() => void runDedupeOnSelection()}
        >
          {dedupeBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
          对选区降重
        </button>
        {selectionText.trim() ? (
          <p className="mt-2 line-clamp-2 text-[10px] text-slate-400">已选：{selectionText.slice(0, 80)}…</p>
        ) : (
          <p className="mt-2 text-[10px] text-slate-400">当前无选区</p>
        )}
      </section>

      <hr className="border-slate-100" />

      <section>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">章节审校</p>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
          基于出版规范与本书设定，对本章已保存正文生成审校报告（逻辑、文风、语病、引用等）。
        </p>
        {chapterTitle ? (
          <p className="mt-2 text-xs font-medium text-ink">{chapterTitle}</p>
        ) : null}
        <button
          type="button"
          className="btn-secondary mt-3 flex h-9 w-full items-center justify-center gap-2 text-xs"
          disabled={reviewing || chapterIndex == null}
          onClick={() => void runReview()}
        >
          {reviewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
          {reviewing ? "审校中…" : "开始审校本章"}
        </button>
      </section>

      {report ? (
        <section className="space-y-3 border-t border-slate-100 pt-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-slate-500">质量评分</span>
            <span className={`text-lg font-semibold ${scoreColor(report.score)}`}>{report.score}</span>
          </div>
          <p className="text-xs leading-relaxed text-slate-600">{report.summary}</p>
          {report.citation_issues && report.citation_issues.length > 0 ? (
            <div className="space-y-2">
              <p className="text-xs font-medium text-red-800">引用 / 来源问题（程序化检测）</p>
              <ul className="max-h-[160px] space-y-1.5 overflow-y-auto">
                {report.citation_issues.map((c: CitationLintIssue, i: number) => (
                  <li key={i} className="rounded border border-red-200 bg-red-50/80 p-2 text-[10px] text-red-900">
                    <span className="font-medium">{c.kind}</span>
                    {c.quote ? <p className="mt-1 italic">「{c.quote}」</p> : null}
                    <p className="mt-0.5">{c.detail}</p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {report.issues.length === 0 && !(report.citation_issues?.length) ? (
            <p className="flex items-center gap-1 text-xs text-emerald-700">
              <ShieldCheck className="h-3.5 w-3.5" />
              未发现需修改项
            </p>
          ) : report.issues.length > 0 ? (
            <ul className="max-h-[320px] space-y-2 overflow-y-auto pr-1">
              {report.issues.map((issue: ReviewIssue) => (
                <IssueCard
                  key={issue.id}
                  bookId={bookId}
                  chapterIndex={chapterIndex}
                  issue={issue}
                  chapterContext={chapterContext}
                  onApply={onApplySuggestion}
                  onAiPreviewReady={onAiPreviewReady}
                />
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function IssueCard({
  bookId,
  chapterIndex,
  issue,
  chapterContext,
  onApply,
  onAiPreviewReady,
}: {
  bookId: string;
  chapterIndex: number | null;
  issue: ReviewIssue;
  chapterContext: string;
  onApply?: (quote: string, suggestion: string) => void;
  onAiPreviewReady?: (payload: EditorAiPreviewPayload) => boolean | void;
}) {
  const sev = issue.severity || "medium";
  const action: ReviewActionType = issue.action_type ?? "revise";
  const [applying, setApplying] = useState(false);

  async function tryApply() {
    if (chapterIndex == null) {
      toast.error("请先选择章节");
      return;
    }
    if (action !== "insert" && !issue.quote.trim()) {
      toast.error("该条建议缺少可定位原文");
      return;
    }
    if (action === "replace" && !issue.suggestion.trim()) {
      toast.error("该条建议缺少可替换正文");
      return;
    }
    setApplying(true);
    try {
      const res = await applyReviewIssue(bookId, chapterIndex, {
        action_type: action,
        quote: issue.quote,
        suggestion: issue.suggestion,
        detail: issue.detail,
        context: chapterContext,
      });
      const previewKind = res.preview_kind === "insert" ? "insert" : "replace";
      const suggestion =
        res.preview_kind === "delete" ? "" : cleanSuggestionText(res.result_text);
      if (
        onAiPreviewReady?.({
          quote: res.quote || issue.quote,
          suggestion,
          kind: previewKind,
        })
      ) {
        toast.success(
          action === "revise" || action === "insert"
            ? "已生成 AI 修改预览，请确认后应用"
            : "已在正文中定位，请确认后应用",
        );
        return;
      }
      if (issue.quote && suggestion) onApply?.(issue.quote, suggestion);
      else toast.error("未在正文中定位到片段");
    } catch {
      toast.error("处理建议失败，请稍后重试");
    } finally {
      setApplying(false);
    }
  }

  const canApply =
    chapterIndex != null &&
    (action === "delete"
      ? !!issue.quote.trim()
      : action === "insert"
        ? !!issue.suggestion.trim() || !!issue.detail.trim()
        : action === "replace"
          ? !!issue.quote.trim() && !!issue.suggestion.trim()
          : !!issue.quote.trim() && (!!issue.suggestion.trim() || !!issue.detail.trim()));

  return (
    <li className={`rounded-lg border p-2.5 text-xs ${SEVERITY_CLASS[sev] ?? SEVERITY_CLASS.medium}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-semibold">{issue.title}</span>
        <span className="rounded bg-white/60 px-1 py-0.5 text-[10px]">
          {REVIEW_SEVERITY_LABEL[issue.severity]}
        </span>
        <span className="rounded bg-white/60 px-1 py-0.5 text-[10px]">
          {REVIEW_CATEGORY_LABEL[issue.category]}
        </span>
        <span className="rounded bg-violet-100 px-1 py-0.5 text-[10px] text-violet-800">
          {REVIEW_ACTION_LABEL[action]}
        </span>
      </div>
      <p className="mt-1.5 leading-relaxed opacity-90">{issue.detail}</p>
      {issue.quote ? (
        <p className="mt-1.5 rounded bg-white/50 px-2 py-1 text-[10px] italic leading-relaxed">
          「{issue.quote}」
        </p>
      ) : null}
      {issue.suggestion ? (
        <p className="mt-1.5 text-[10px] leading-relaxed">
          <span className="font-medium">建议：</span>
          {issue.suggestion}
        </p>
      ) : null}
      {canApply && (onApply || onAiPreviewReady) ? (
        <button
          type="button"
          className="mt-2 flex items-center gap-1 text-[10px] font-medium text-violet-800 hover:underline disabled:opacity-50"
          disabled={applying}
          onClick={() => void tryApply()}
        >
          {applying ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
          {action === "revise" || action === "insert"
            ? "生成修改预览"
            : action === "delete"
              ? "预览删除"
              : "定位并预览替换"}
        </button>
      ) : null}
    </li>
  );
}
