import type { BookJob, BookJobDetail } from "@/api/bookJobs";

export type AutoBookStageId =
  | "setting"
  | "literature"
  | "outline"
  | "narrative"
  | "writing"
  | "figures"
  | "done";

export type AutoBookStageState = "pending" | "active" | "done";

export interface AutoBookStage {
  id: AutoBookStageId;
  label: string;
}

export const AUTO_BOOK_STAGES: AutoBookStage[] = [
  { id: "setting", label: "书稿设定" },
  { id: "literature", label: "文献规划" },
  { id: "outline", label: "大纲生成" },
  { id: "narrative", label: "叙事宪法" },
  { id: "writing", label: "章节写作" },
  { id: "figures", label: "图像生成" },
  { id: "done", label: "全书检查" },
];

const STEP_ORDER: Record<string, number> = {
  setting: 0,
  literature: 1,
  outline: 2,
  narrative: 3,
  preface: 4,
  writing: 4,
  bibliography: 6,
  figures: 5,
  done: 6,
};

function stepIndex(step: string | null | undefined): number {
  if (!step) return -1;
  return STEP_ORDER[step] ?? -1;
}

export function stageState(stageId: AutoBookStageId, job: BookJob | null | undefined): AutoBookStageState {
  if (!job) return "pending";
  const detail = job.detail;
  const current = stepIndex(job.current_step);
  const target = STEP_ORDER[stageId] ?? 0;

  if (job.status === "completed") return "done";
  if (job.status === "failed") {
    if (current > target) return "done";
    if (current === target) return "active";
    return "pending";
  }

  if (stageId === "setting" && current >= 0) return current > 0 ? "done" : "active";
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
    if (detail?.narrative_ready || current > 3) return "done";
    if (current === 3) return "active";
    return "pending";
  }
  if (stageId === "writing") {
    if (job.current_step === "bibliography" || job.current_step === "figures" || job.current_step === "done") {
      return "done";
    }
    if (detail?.writing_started || job.current_step === "writing" || job.current_step === "preface") return "active";
    return "pending";
  }
  if (stageId === "figures") {
    if (job.status === "completed") return "done";
    if (job.current_step === "figures") return "active";
    if (job.current_step === "done") return "done";
    if ((detail?.figures_total ?? 0) > 0 && (detail?.figures_done ?? 0) >= (detail?.figures_total ?? 0)) return "done";
    return "pending";
  }
  if (stageId === "done") {
    if (job.status === "completed") return "done";
    if (job.current_step === "bibliography") return "active";
    return "pending";
  }

  if (current > target) return "done";
  if (current === target) return "active";
  return "pending";
}

export function shouldEnterEditor(job: BookJob | null | undefined): boolean {
  if (!job) return false;
  const d: BookJobDetail | null | undefined = job.detail;
  return Boolean(
    d?.ready_for_editor &&
      d.outline_ready &&
      d.narrative_ready &&
      (d.total_chapters ?? 0) > 0 &&
      (job.current_step === "writing" ||
        job.current_step === "preface" ||
        job.current_step === "bibliography" ||
        job.current_step === "figures" ||
        job.current_step === "done" ||
        d.writing_started),
  );
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
  const weights = [8, 10, 18, 12, 40, 10, 2];
  let pct = 0;
  AUTO_BOOK_STAGES.forEach((stage, i) => {
    const st = stageState(stage.id, job);
    if (st === "done") pct += weights[i] ?? 0;
    else if (st === "active") pct += Math.round((weights[i] ?? 0) * 0.45);
  });
  return Math.min(99, Math.max(job.progress_pct ?? 0, pct));
}
