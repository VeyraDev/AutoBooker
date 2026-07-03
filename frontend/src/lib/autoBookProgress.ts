import type { BookJob } from "@/api/bookJobs";

export type AutoBookStageId = "setting" | "literature" | "outline" | "narrative";

export type AutoBookStageState = "pending" | "active" | "done";

export interface AutoBookStage {
  id: AutoBookStageId;
  label: string;
}

/** 进度页仅展示前置阶段；章节写作在写作页走正常 SSE 批量流程 */
export const AUTO_BOOK_STAGES: AutoBookStage[] = [
  { id: "setting", label: "书稿设定" },
  { id: "literature", label: "文献规划" },
  { id: "outline", label: "大纲生成" },
  { id: "narrative", label: "写作规则" },
];

const STEP_ORDER: Record<string, number> = {
  setting: 0,
  literature: 1,
  outline: 2,
  narrative: 3,
  preface: 3,
  done: 4,
};

function stepIndex(step: string | null | undefined): number {
  if (!step) return -1;
  return STEP_ORDER[step] ?? -1;
}

export function stageState(stageId: AutoBookStageId, job: BookJob | null | undefined): AutoBookStageState {
  if (!job) return "pending";
  const detail = job.detail;
  const current = stepIndex(job.current_step);

  if (job.status === "completed") return "done";
  if (job.status === "failed") {
    const target = STEP_ORDER[stageId] ?? 0;
    if (current > target) return "done";
    if (current === target) return "active";
    return "pending";
  }

  if (stageId === "setting") return current > 0 ? "done" : current === 0 ? "active" : "pending";
  if (stageId === "literature") {
    if (current > 1) return "done";
    if (current === 1) return "active";
    return "pending";
  }
  if (stageId === "outline") {
    if (detail?.outline_ready || current > 2) return "done";
    if (current === 2) return "active";
    return "pending";
  }
  if (stageId === "narrative") {
    if (detail?.narrative_ready || job.status === "completed") return "done";
    if (current === 3) return "active";
    return "pending";
  }

  return "pending";
}

/** 全书写作规则完成后进入写作页（章节由前端流式批量生成） */
export function shouldEnterEditor(job: BookJob | null | undefined): boolean {
  if (!job || job.status !== "completed") return false;
  const d = job.detail;
  return Boolean(d?.narrative_ready && d.outline_ready && (d.total_chapters ?? 0) > 0);
}

export function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m <= 0) return `${s} 秒`;
  return `${m} 分 ${s.toString().padStart(2, "0")} 秒`;
}

export function estimateProgressPct(job: BookJob | null | undefined): number {
  if (!job) return 0;
  if (job.status === "completed") return 100;
  const weights = [15, 20, 35, 30];
  let pct = 0;
  AUTO_BOOK_STAGES.forEach((stage, i) => {
    const st = stageState(stage.id, job);
    if (st === "done") pct += weights[i] ?? 0;
    else if (st === "active") pct += Math.round((weights[i] ?? 0) * 0.5);
  });
  return Math.min(99, Math.max(job.progress_pct ?? 0, pct));
}
