import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle, Loader2, AlertCircle } from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Link, useNavigate, useParams } from "react-router-dom";

import { fetchBookJob, startAutoGenerateForBook } from "@/api/bookJobs";
import { getBook } from "@/api/books";
import {
  AUTO_BOOK_STAGES,
  estimateProgressPct,
  formatElapsed,
  shouldEnterEditor,
  stageState,
} from "@/lib/autoBookProgress";
import { markPendingAutoWrite } from "@/lib/autoBookWrite";

function StageIcon({ state }: { state: "pending" | "active" | "done" }) {
  if (state === "done") return <CheckCircle2 className="h-5 w-5 text-emerald-600" />;
  if (state === "active") return <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />;
  return <Circle className="h-5 w-5 text-slate-300" />;
}

export default function AutoBookProgressPage() {
  const { bookId } = useParams();
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);

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

  async function retryStart() {
    if (!bookId || starting) return;
    setStarting(true);
    try {
      await startAutoGenerateForBook(bookId);
      toast.success("一键成书已重新启动");
      await Promise.all([bookQuery.refetch(), jobQuery.refetch()]);
    } catch {
      toast.error("未能启动一键成书，请检查网络后重试");
    } finally {
      setStarting(false);
    }
  }

  useEffect(() => {
    if (!bookId || !job) return;
    if (shouldEnterEditor(job)) {
      markPendingAutoWrite(bookId);
      navigate(`/app/books/${bookId}`, { replace: true });
    }
  }, [bookId, job, navigate]);

  if (!bookId) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16 text-center text-sm text-slate-500">
        未找到该书稿
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
        <p className="mt-2 text-sm text-slate-500">完成前期准备后将进入写作页，正文和配图会继续自动生成。</p>

        <div className="mt-6">
          <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
            <span>当前进度</span>
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
            正在获取进度…
          </p>
        ) : null}

        {!jobQuery.isLoading && !jobQuery.isError && !job ? (
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <p className="font-medium">生成任务尚未启动</p>
            <p className="mt-1 text-xs">书稿已经保留，可以在这里重新启动，不会返回设定页。</p>
            <button
              type="button"
              className="btn-primary mt-3 text-xs"
              disabled={starting}
              onClick={() => void retryStart()}
            >
              {starting ? "正在启动…" : "重新开始一键成书"}
            </button>
          </div>
        ) : null}

        {jobQuery.isError ? (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <p className="font-medium">暂时无法获取生成进度</p>
            <button
              type="button"
              className="btn-secondary mt-3 text-xs"
              onClick={() => void jobQuery.refetch()}
            >
              重新获取进度
            </button>
          </div>
        ) : null}

        {job?.status === "failed" ? (
          <div className="mt-6 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">生成未能继续</p>
              <p className="mt-1 text-xs">暂时无法继续，请稍后重试</p>
              <Link to={`/app/books/${bookId}`} className="mt-3 inline-block text-xs text-red-700 underline">
                返回书稿设定
              </Link>
            </div>
          </div>
        ) : null}

        {shouldEnterEditor(job) ? (
          <p className="mt-6 text-center text-xs text-slate-400">即将进入写作页…</p>
        ) : null}
      </div>
    </div>
  );
}
