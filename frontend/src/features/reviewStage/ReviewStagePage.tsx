import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import toast from "react-hot-toast";
import { client } from "@/api/client";

async function fetchFindings(bookId: string) {
  const { data } = await client.get(`/books/${bookId}/review-stage/findings`);
  return data;
}

async function runReview(bookId: string) {
  const { data } = await client.post(`/books/${bookId}/review-stage/run`);
  return data;
}

async function patchFinding(bookId: string, findingId: string, status: string) {
  const { data } = await client.patch(`/books/${bookId}/review-stage/findings/${findingId}`, { status });
  return data;
}

type ReviewStagePageProps = {
  bookId: string;
  onCompleteBook?: () => void | Promise<void>;
  completing?: boolean;
};

export default function ReviewStagePage({ bookId, onCompleteBook, completing = false }: ReviewStagePageProps) {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"writing" | "publication">("writing");

  const summaryQ = useQuery({
    queryKey: ["reviewStage", bookId],
    queryFn: async () => (await client.get(`/books/${bookId}/review-stage/summary`)).data,
  });

  const findingsQ = useQuery({
    queryKey: ["reviewFindings", bookId],
    queryFn: () => fetchFindings(bookId),
  });

  const runMut = useMutation({
    mutationFn: () => runReview(bookId),
    onSuccess: () => {
      toast.success("审校完成");
      void qc.invalidateQueries({ queryKey: ["reviewStage", bookId] });
      void qc.invalidateQueries({ queryKey: ["reviewFindings", bookId] });
    },
    onError: () => toast.error("审校失败"),
  });

  const wq = summaryQ.data?.tracks?.writing_quality;
  const pub = summaryQ.data?.tracks?.publication_standard;
  const findings = (findingsQ.data?.findings || []) as Array<{
    id: string;
    track: string;
    title: string;
    detail?: string;
    severity: string;
    status: string;
  }>;
  const filtered = findings.filter((f) => (tab === "writing" ? f.track === "writing_quality" : f.track === "publication_standard"));

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
        审校用于发现修改建议，不影响全书完成或导出。你可以跳过、稍后处理或直接导出。
      </p>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">审校</h2>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="rounded bg-brand px-3 py-1.5 text-sm text-white" disabled={runMut.isPending} onClick={() => runMut.mutate()}>
            {runMut.isPending ? "运行中…" : "运行审校"}
          </button>
          {onCompleteBook ? (
            <button
              type="button"
              className="rounded border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={completing}
              onClick={() => void onCompleteBook()}
            >
              {completing ? "正在完成…" : "完成全书"}
            </button>
          ) : null}
        </div>
      </div>
      <div className="flex gap-2 border-b">
        <button type="button" className={`px-3 py-2 text-sm ${tab === "writing" ? "border-b-2 border-brand font-medium" : ""}`} onClick={() => setTab("writing")}>
          写作质量
        </button>
        <button type="button" className={`px-3 py-2 text-sm ${tab === "publication" ? "border-b-2 border-brand font-medium" : ""}`} onClick={() => setTab("publication")}>
          出版规范
        </button>
      </div>
      {tab === "writing" ? (
        <section className="rounded-lg border p-4 text-sm">
          <p>状态：{wq?.status === "completed" ? "已审校" : "待审校"}</p>
          {wq?.reviewed_chapters != null ? <p>已审章节 {wq.reviewed_chapters}/{wq.total_chapters}</p> : null}
          {wq?.average_score != null ? <p>平均分 {Number(wq.average_score).toFixed(1)}</p> : null}
        </section>
      ) : (
        <section className="rounded-lg border p-4 text-sm">
          <p>状态：{pub?.status === "completed" ? "已审校" : "待审校"}</p>
          {pub?.structure_suggestion_count != null ? <p>结构建议 {pub.structure_suggestion_count} 条</p> : null}
        </section>
      )}
      <ul className="space-y-2">
        {filtered.map((f) => (
          <li key={f.id} className="rounded border p-3 text-sm">
            <div className="font-medium">{f.title}</div>
            {f.detail ? <p className="text-slate-600">{f.detail}</p> : null}
            {f.status === "open" ? (
              <div className="mt-2 flex gap-2">
                <button type="button" className="text-xs text-slate-500" onClick={() => void patchFinding(bookId, f.id, "dismissed").then(() => findingsQ.refetch())}>
                  忽略
                </button>
                <button type="button" className="text-xs text-brand" onClick={() => void patchFinding(bookId, f.id, "resolved").then(() => findingsQ.refetch())}>
                  已处理
                </button>
              </div>
            ) : null}
          </li>
        ))}
        {!filtered.length ? <li className="text-sm text-slate-500">暂无 findings</li> : null}
      </ul>
    </div>
  );
}
