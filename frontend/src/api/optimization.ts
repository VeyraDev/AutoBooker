import { client } from "@/api/client";

export type OptimizationProject = {
  id: string;
  book_id: string;
  source_file_id: string;
  status: string;
  allow_structure_changes: boolean;
  optimization_goals: string[];
  diagnosis: Record<string, unknown> | null;
  optimization_plan: Record<string, unknown> | null;
  baseline_chapters: Array<{ id: string; index: number; title: string; body_text: string; source_locator: Record<string, unknown> }>;
  mappings: Array<{
    id: string;
    baseline_chapter_id: string;
    working_chapter_id: string | null;
    outline_chapter_index: number | null;
    outline_title: string | null;
    confidence: number;
    status: string;
  }>;
  revisions: Array<{
    id: string;
    baseline_chapter_id: string;
    status: string;
    source: string;
    summary: string | null;
    created_at: string | null;
  }>;
  error_message: string | null;
};

export async function createOptimizationProject(
  file: File,
  goals: string[],
  allowStructureChanges: boolean,
): Promise<OptimizationProject> {
  const form = new FormData();
  form.append("file", file);
  form.append("goals", JSON.stringify(goals));
  form.append("allow_structure_changes", String(allowStructureChanges));
  const { data } = await client.post<OptimizationProject>("/books/optimization-projects", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  });
  return data;
}

export async function getOptimizationProject(bookId: string): Promise<OptimizationProject> {
  const { data } = await client.get<OptimizationProject>(`/books/${bookId}/optimization`);
  return data;
}

export async function confirmOptimizationMapping(bookId: string, project: OptimizationProject): Promise<OptimizationProject> {
  const { data } = await client.post<OptimizationProject>(`/books/${bookId}/optimization/mapping/confirm`, {
    mappings: project.mappings.map((x) => ({
      baseline_chapter_id: x.baseline_chapter_id,
      outline_chapter_index: x.outline_chapter_index,
      outline_title: x.outline_title,
      confirmed: true,
    })),
  });
  return data;
}

export async function diagnoseOptimization(bookId: string): Promise<OptimizationProject> {
  const { data } = await client.post<OptimizationProject>(`/books/${bookId}/optimization/diagnose`);
  return data;
}

export async function runOptimization(bookId: string): Promise<{ id: string; status: string }> {
  const { data } = await client.post(`/books/${bookId}/optimization/run`);
  return data;
}

export async function optimizeChapter(
  bookId: string,
  baselineChapterId: string,
  instruction = "",
): Promise<{ id: string; status: string }> {
  const { data } = await client.post(`/books/${bookId}/optimization/chapters`, {
    baseline_chapter_id: baselineChapterId,
    instruction,
  });
  return data;
}

export async function getOptimizationJob(bookId: string, jobId: string) {
  const { data } = await client.get<{
    id: string;
    status: string;
    progress_pct: number;
    current_chapter_index: number | null;
    error_message: string | null;
  }>(`/books/${bookId}/optimization/jobs/${jobId}`);
  return data;
}

export async function compareOptimizationRevision(bookId: string, revisionId: string) {
  const { data } = await client.get<{
    original: string;
    revised: string;
    diff: Array<{ type: string; original: string; revised: string }>;
  }>(`/books/${bookId}/optimization/revisions/${revisionId}/compare`);
  return data;
}

export async function decideOptimizationRevision(bookId: string, revisionId: string, action: "accept" | "reject") {
  const { data } = await client.post(`/books/${bookId}/optimization/revisions/${revisionId}/${action}`);
  return data;
}

export async function restoreOptimizationBaseline(bookId: string, baselineId: string) {
  const { data } = await client.post(`/books/${bookId}/optimization/chapters/${baselineId}/restore`);
  return data;
}
