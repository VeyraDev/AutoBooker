import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle, Loader2, AlertCircle } from "lucide-react";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { fetchBookJob, type BookJob } from "@/api/bookJobs";
import { getBook } from "@/api/books";
import {
  AUTO_BOOK_STAGES,
  estimateProgressPct,
  formatElapsed,
  shouldEnterEditor,
  stageState,
} from "@/lib/autoBookProgress";

function StageIcon({ state }: { state: "pending" | "active" | "done" }) {
  if (state === "done") return <CheckCircle2 className="h-5 w-5 text-emerald-600" />;
  if (state === "active") return <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />;
  return <Circle className="h-5 w-5 text-slate-300" />;
}

function ProgressDetail({ job }: { job: BookJob }) {
  const d = job.detail;
  if (!d) return null;

  if (job.current_step === "writing" || job.current_step === "preface") {
    return (
      <div className="mt-4 space-y-1 text-sm text-slate-600">
        <p>
          正文：{d.chapters_done} / {d.total_chapters} 章
          {d.current_chapter_index ? ` · 当前第 ${d.current_chapter_index} 章` : null}
        </p>
        {(d.figures_total ?? 0) > 0 ? (
          <p>
            图片：{d.figures_done} / {d.figures_total} 张完成
          </p>
        ) : null}
      </div>
    );
  }

  if (job.current_step === "figures") {
    return (
      <div className="mt-4 text-sm text-slate-600">
        <p>正文已全部完成</p>
        <p className="mt-1">
          图片：{d.figures_done} / {d.figures_total} 张完成
        </p>
      </div>
    );
  }

  if (d.stage_message) {
    return <p className="mt-4 text-sm text-slate-600">{d.stage_message}</p>;
  }

  return null;
}

export default function AutoBookProgressPage() {
  const { bookId } = useParams();
  const navigate = useNavigate();

  const bookQuery = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId!),
    enabled: !!bookId,
  });

  const jobQuery = useQuery({
    queryKey: ["bookJob", bookId],
    queryFn: () => fetchBookJob(bookId!),
    enabled: !!bookId,
    refetchInterval: (q) => {
      const job = q.state.data;
      if (!job) return 3000;
      if (job.status === "completed" || job.status === "failed") return false;
      return 2500;
    },
  });

  const job = jobQuery.data ?? null;
  const bookTitle = job?.detail?.book_title || bookQuery.data?.title || "书稿";
  const pct = estimateProgressPct(job);

  useEffect(() => {
    if (!bookId || !job) return;
    if (shouldEnterEditor(job)) {
      navigate(`/app/books/${bookId}`, { replace: true });
    }
  }, [bookId, job, navigate]);

  if (!bookId) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16 text-center text-sm text-slate-500">
        无效的书稿 ID
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <div className="mb-6 flex items-center gap-3">
        <Link to="/app/books" className="text-sm text-slate-500 hover:text-brand">
          ← 返回列表
        </Link>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-xs font-medium uppercase tracking-wide text-indigo-600">一键成书</p>
        <h1 className="mt-2 text-xl font-semibold text-ink">正在生成《{bookTitle}》</h1>

        <div className="mt-6">
          <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
            <span>总体进度</span>
            <span>{pct}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-indigo-600 transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          {job?.detail?.elapsed_seconds != null ? (
            <p className="mt-2 text-xs text-slate-400">已运行 {formatElapsed(job.detail.elapsed_seconds)}</p>
          ) : null}
        </div>

        <ul className="mt-8 space-y-3">
          {AUTO_BOOK_STAGES.map((stage) => {
            const state = stageState(stage.id, job);
            return (
              <li
                key={stage.id}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 ${
                  state === "active" ? "bg-indigo-50/80" : ""
                }`}
              >
                <StageIcon state={state} />
                <span
                  className={`text-sm ${
                    state === "done"
                      ? "text-slate-700"
                      : state === "active"
                        ? "font-medium text-indigo-900"
                        : "text-slate-400"
                  }`}
                >
                  {stage.label}
                </span>
              </li>
            );
          })}
        </ul>

        {jobQuery.isLoading ? (
          <p className="mt-6 flex items-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在连接任务状态…
          </p>
        ) : null}

        {job ? <ProgressDetail job={job} /> : null}

        {job?.status === "failed" ? (
          <div className="mt-6 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">生成失败</p>
              <p className="mt-1 text-xs">{job.error_message || "未知错误"}</p>
              <Link to={`/app/books/${bookId}`} className="mt-3 inline-block text-xs text-red-700 underline">
                进入书稿设定页排查
              </Link>
            </div>
          </div>
        ) : null}

        {job?.status === "completed" ? (
          <div className="mt-6 text-center">
            <p className="text-sm text-emerald-700">全书生成任务已完成</p>
            <button
              type="button"
              className="btn-primary mt-4"
              onClick={() => navigate(`/app/books/${bookId}`)}
            >
              进入写作页
            </button>
          </div>
        ) : null}

        {shouldEnterEditor(job) ? (
          <p className="mt-6 text-center text-xs text-slate-400">即将进入写作页…</p>
        ) : null}
      </div>
    </div>
  );
}
