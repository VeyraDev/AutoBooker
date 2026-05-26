import { Loader2, ShieldCheck, Wand2 } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";

import { reviewChapter } from "@/api/review";
import { editChapterSelection, type SelectionEditMode } from "@/api/chapters";
import type { ChapterReviewResult, ReviewIssue } from "@/types/review";
import { REVIEW_CATEGORY_LABEL, REVIEW_SEVERITY_LABEL } from "@/types/review";

type Props = {
  bookId: string;
  chapterIndex: number | null;
  chapterTitle?: string;
  /** 编辑器当前选区纯文本 */
  selectionText?: string;
  onApplySuggestion?: (quote: string, suggestion: string) => void;
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
}: Props) {
  const [reviewing, setReviewing] = useState(false);
  const [dedupeBusy, setDedupeBusy] = useState(false);
  const [report, setReport] = useState<ChapterReviewResult | null>(null);

  async function runReview() {
    if (chapterIndex == null) {
      toast.error("请先选择章节");
      return;
    }
    setReviewing(true);
    try {
      const res = await reviewChapter(bookId, chapterIndex);
      setReport(res);
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
      onApplySuggestion?.(text, out.trim());
      toast.success("已生成降重文本，请确认后保留");
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
          {report.issues.length === 0 ? (
            <p className="flex items-center gap-1 text-xs text-emerald-700">
              <ShieldCheck className="h-3.5 w-3.5" />
              未发现需修改项
            </p>
          ) : (
            <ul className="max-h-[320px] space-y-2 overflow-y-auto pr-1">
              {report.issues.map((issue: ReviewIssue) => (
                <IssueCard key={issue.id} issue={issue} onApply={onApplySuggestion} />
              ))}
            </ul>
          )}
        </section>
      ) : null}
    </div>
  );
}

function IssueCard({
  issue,
  onApply,
}: {
  issue: ReviewIssue;
  onApply?: (quote: string, suggestion: string) => void;
}) {
  const sev = issue.severity || "medium";
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
      {issue.quote && issue.suggestion && onApply ? (
        <button
          type="button"
          className="mt-2 text-[10px] font-medium text-violet-800 hover:underline"
          onClick={() => onApply(issue.quote, issue.suggestion)}
        >
          在编辑器中尝试替换
        </button>
      ) : null}
    </li>
  );
}
