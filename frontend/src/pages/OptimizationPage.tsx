import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  compareOptimizationRevision,
  confirmOptimizationMapping,
  decideOptimizationRevision,
  diagnoseOptimization,
  getOptimizationJob,
  getOptimizationProject,
  optimizeChapter,
  restoreOptimizationBaseline,
  runOptimization,
} from "@/api/optimization";
import { listReferences, uploadReference } from "@/api/references";
import type { FilePurpose } from "@/types/reference";

export default function OptimizationPage() {
  const { bookId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [compare, setCompare] = useState<{ original: string; revised: string } | null>(null);
  const [auxPurpose, setAuxPurpose] = useState<Exclude<FilePurpose, "source_manuscript">>("reference_material");
  const [jobProgress, setJobProgress] = useState<number | null>(null);
  const query = useQuery({
    queryKey: ["optimization", bookId],
    queryFn: () => getOptimizationProject(bookId!),
    enabled: !!bookId,
    refetchInterval: (q) => ["parsing", "analyzing", "optimizing"].includes(q.state.data?.status ?? "") ? 2000 : false,
  });
  const project = query.data;
  const referencesQuery = useQuery({
    queryKey: ["references", bookId],
    queryFn: () => listReferences(bookId!),
    enabled: !!bookId,
    refetchInterval: (q) =>
      q.state.data?.some((file) => ["pending", "processing"].includes(file.parse_status))
        ? 2000
        : false,
  });

  async function act(fn: () => Promise<unknown>, message: string) {
    setBusy(true);
    try {
      await fn();
      await qc.invalidateQueries({ queryKey: ["optimization", bookId] });
      toast.success(message);
    } catch {
      toast.error("操作未能完成，请稍后重试");
    } finally {
      setBusy(false);
    }
  }

  async function startAll() {
    if (!bookId) return;
    setBusy(true);
    try {
      const job = await runOptimization(bookId);
      let state = await getOptimizationJob(bookId, job.id);
      while (["pending", "running"].includes(state.status)) {
        setJobProgress(state.progress_pct);
        await new Promise((resolve) => window.setTimeout(resolve, 1800));
        state = await getOptimizationJob(bookId, job.id);
      }
      if (state.status === "failed") throw new Error(state.error_message ?? "");
      await qc.invalidateQueries({ queryKey: ["optimization", bookId] });
      toast.success("全书优化候选版本已生成");
    } catch {
      toast.error("优化任务未能继续，请稍后重试");
    } finally {
      setJobProgress(null);
      setBusy(false);
    }
  }

  async function uploadAuxiliary(file: File) {
    if (!bookId) return;
    setBusy(true);
    try {
      await uploadReference(bookId, file, {
        filePurposes: [auxPurpose],
        outlineUsage: auxPurpose === "outline" ? "reference" : undefined,
      });
      await referencesQuery.refetch();
      toast.success("辅助资料已上传，正在解析");
    } catch {
      toast.error("未能上传辅助资料，请重试");
    } finally {
      setBusy(false);
    }
  }

  if (!bookId) return <p className="p-8 text-sm text-slate-500">未找到该书稿</p>;
  if (query.isLoading || !project) {
    return <div className="flex items-center justify-center gap-2 py-24 text-sm text-slate-500"><Loader2 className="h-5 w-5 animate-spin" />正在解析原始书稿…</div>;
  }

  return (
    <section className="mx-auto max-w-5xl space-y-5 px-5 py-8">
      <Link to="/app/books" className="text-sm text-slate-500 hover:text-violet-700">← 返回我的书稿</Link>
      <div>
        <p className="eyebrow">优化已有书稿</p>
        <h1 className="page-title mt-2">优化工作流</h1>
        <p className="page-subtitle">原稿基线不会被覆盖；所有优化先生成候选版本，再由你决定是否接受。</p>
      </div>

      {project.status === "failed" ? <div className="state-panel text-red-700">{project.error_message}</div> : null}

      <div className="card p-5">
        <h2 className="font-medium text-ink">辅助资料</h2>
        <p className="mt-1 text-xs text-slate-500">可选上传参考大纲、写作要求、参考资料或参考文献。原始书稿不会作为参考资料使用。</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select
            className="input h-9 w-auto text-sm"
            value={auxPurpose}
            onChange={(event) => setAuxPurpose(event.target.value as Exclude<FilePurpose, "source_manuscript">)}
          >
            <option value="outline">参考大纲</option>
            <option value="writing_requirements">写作要求</option>
            <option value="reference_material">参考资料</option>
            <option value="bibliography">参考文献</option>
          </select>
          <label className="btn-secondary cursor-pointer text-sm">
            上传文件
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              className="hidden"
              disabled={busy}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void uploadAuxiliary(file);
              }}
            />
          </label>
        </div>
        {referencesQuery.data?.filter((file) => file.id !== project.source_file_id).length ? (
          <ul className="mt-3 space-y-1 text-xs text-slate-600">
            {referencesQuery.data
              .filter((file) => file.id !== project.source_file_id)
              .map((file) => (
                <li key={file.id}>
                  {file.filename} ·
                  {file.lifecycle_status === "pending_confirmation"
                    ? " 待确认"
                    : file.parse_status === "done"
                      ? " 已生效"
                      : file.parse_status === "failed"
                        ? " 解析失败，请重新上传"
                        : " 正在解析…"}
                </li>
              ))}
          </ul>
        ) : null}
      </div>

      <div className="card p-5">
        <h2 className="font-medium text-ink">原始书稿与章节对应</h2>
        <p className="mt-1 text-xs text-slate-500">已识别 {project.baseline_chapters.length} 章；仅不确定的对应关系需要调整。</p>
        <div className="mt-4 max-h-[360px] space-y-2 overflow-y-auto">
          {project.baseline_chapters.map((chapter) => {
            const mapping = project.mappings.find((x) => x.baseline_chapter_id === chapter.id);
            return (
              <div key={chapter.id} className="rounded-lg border border-slate-100 bg-white p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span>{chapter.index}. {chapter.title}</span>
                  <span className={mapping?.status === "needs_confirmation" ? "text-amber-700" : "text-emerald-700"}>
                    {mapping?.status === "needs_confirmation" ? "待确认" : "已对应"}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-slate-500">{chapter.body_text || "（本章无正文）"}</p>
              </div>
            );
          })}
        </div>
        {project.status === "mapping_review" ? (
          <button className="btn-primary mt-4" disabled={busy} onClick={() => void act(() => confirmOptimizationMapping(bookId, project), "章节对应关系已确认")}>确认章节对应关系</button>
        ) : null}
      </div>

      {["ready_for_analysis", "plan_ready", "editing", "completed"].includes(project.status) ? (
        <div className="card p-5">
          <h2 className="font-medium text-ink">全书诊断与优化方案</h2>
          {project.diagnosis ? (
            <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-3">
              <p className="rounded-lg bg-slate-50 p-3">
                章节数量：{String((project.diagnosis.structure as { chapter_count?: number } | undefined)?.chapter_count ?? "—")}
              </p>
              <p className="rounded-lg bg-slate-50 p-3">
                重复内容：{Array.isArray(project.diagnosis.duplicate_content) ? project.diagnosis.duplicate_content.length : 0} 处
              </p>
              <p className="rounded-lg bg-slate-50 p-3">
                待补充引用：{Array.isArray(project.diagnosis.citation_gaps) ? project.diagnosis.citation_gaps.length : 0} 章
              </p>
            </div>
          ) : <p className="mt-2 text-sm text-slate-500">尚未生成诊断。</p>}
          {project.optimization_plan && Array.isArray(project.optimization_plan.steps) ? (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-600">
              {(project.optimization_plan.steps as string[]).map((step) => <li key={step}>{step}</li>)}
            </ul>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <button className="btn-secondary" disabled={busy} onClick={() => void act(() => diagnoseOptimization(bookId), "优化方案已生成")}>生成优化方案</button>
            {project.optimization_plan ? <button className="btn-primary" disabled={busy} onClick={() => void startAll()}>开始优化</button> : null}
          </div>
          {jobProgress != null ? <p className="mt-3 text-xs text-violet-700">正在按章节优化：{jobProgress}%</p> : null}
        </div>
      ) : null}

      {["plan_ready", "editing"].includes(project.status) ? (
        <div className="card p-5">
          <h2 className="font-medium text-ink">逐章优化</h2>
          <div className="mt-3 space-y-2">
            {project.baseline_chapters.map((chapter) => (
              <div key={chapter.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 p-3 text-sm">
                <span>{chapter.index}. {chapter.title}</span>
                <button
                  type="button"
                  className="text-xs text-violet-700 hover:underline"
                  disabled={busy}
                  onClick={() => void act(() => optimizeChapter(bookId, chapter.id), "本章优化候选版本已生成")}
                >
                  优化本章
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {project.revisions.length ? (
        <div className="card p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-medium text-ink">候选修订</h2>
            <button className="btn-secondary text-xs" onClick={() => navigate(`/app/books/${bookId}`)}>进入编辑器</button>
          </div>
          <div className="mt-3 space-y-2">
            {project.revisions.map((revision) => {
              const chapter = project.baseline_chapters.find((x) => x.id === revision.baseline_chapter_id);
              return (
                <div key={revision.id} className="rounded-lg border border-slate-100 p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span>{chapter?.title ?? "章节"} · {revision.status === "proposed" ? "待决定" : revision.status === "accepted" ? "已接受" : "已放弃"}</span>
                    <div className="flex gap-2">
                      <button className="text-xs text-violet-700" onClick={() => void compareOptimizationRevision(bookId, revision.id).then(setCompare)}>比较差异</button>
                      {revision.status === "proposed" ? <>
                        <button className="text-xs text-emerald-700" onClick={() => void act(() => decideOptimizationRevision(bookId, revision.id, "accept"), "已接受修改")}>接受</button>
                        <button className="text-xs text-red-600" onClick={() => void act(() => decideOptimizationRevision(bookId, revision.id, "reject"), "已放弃修改")}>放弃</button>
                      </> : null}
                      <button className="text-xs text-slate-600" onClick={() => void act(() => restoreOptimizationBaseline(bookId, revision.baseline_chapter_id), "已恢复原稿")}>恢复原稿</button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {compare ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={() => setCompare(null)}>
          <div className="grid max-h-[85vh] w-full max-w-5xl grid-cols-1 gap-4 overflow-auto rounded-xl bg-white p-5 md:grid-cols-2" onClick={(e) => e.stopPropagation()}>
            <div><h3 className="mb-2 font-medium">原稿</h3><p className="whitespace-pre-wrap text-sm text-slate-600">{compare.original}</p></div>
            <div><h3 className="mb-2 font-medium">优化稿</h3><p className="whitespace-pre-wrap text-sm text-slate-600">{compare.revised}</p></div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
