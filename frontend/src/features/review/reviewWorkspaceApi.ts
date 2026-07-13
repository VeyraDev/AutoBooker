import { client } from "@/api/client";

export type WorkspaceFindingTier = "must_fix" | "suggest" | "observe";

export type ProductDimension =
  | "goal_alignment"
  | "argument_quality"
  | "structure_progress"
  | "evidence_citation"
  | "language_credibility"
  | "reader_utility"
  | "publication_delivery";

export const PRODUCT_DIMENSION_LABEL: Record<ProductDimension, string> = {
  goal_alignment: "写作目标一致性",
  argument_quality: "中心主旨与论证",
  structure_progress: "结构推进",
  evidence_citation: "事实引用可信度",
  language_credibility: "语言表达",
  reader_utility: "读者可用性",
  publication_delivery: "出版交付",
};

export type WorkspaceFinding = {
  id: string;
  source: "chapter" | "book";
  chapter_index: number | null;
  chapter_title: string | null;
  tier: WorkspaceFindingTier;
  status: string;
  title: string;
  detail: string | null;
  quote: string | null;
  suggestion: string | null;
  basis_refs: string[];
  category: string | null;
  track: string | null;
  detector: string | null;
  dimension: string | null;
  issue_type: string | null;
  product_dimension: ProductDimension | null;
  impact_scope: string | null;
  locatable: boolean;
  task_id: string | null;
  validation_passed: boolean;
  filter_reason: string | null;
  why_it_matters: string | null;
};

export type ReviewTask = {
  id: string;
  book_id: string;
  scope: string;
  chapter_indexes: number[] | null;
  goal: string;
  custom_prompt: string | null;
  adopted_standards: Record<string, boolean>;
  exclusions: string[];
  status: string;
  summary_text: string | null;
  run_id: string | null;
  created_at: string | null;
};

export type ReviewWorkspaceSummary = {
  book_id: string;
  must_fix_count: number;
  suggest_count: number;
  observe_count: number;
  open_count: number;
  run_status: string | null;
  by_chapter: Record<string, number>;
  latest_task: ReviewTask | null;
};

export async function getReviewWorkspaceSummary(bookId: string): Promise<ReviewWorkspaceSummary> {
  const { data } = await client.get<ReviewWorkspaceSummary>(`/books/${bookId}/review-workspace/summary`);
  return data;
}

export async function getReviewTask(bookId: string, taskId: string): Promise<ReviewTask> {
  const { data } = await client.get<ReviewTask>(`/books/${bookId}/review-workspace/tasks/${taskId}`);
  return data;
}

export async function listReviewWorkspaceFindings(
  bookId: string,
  params?: {
    tier?: WorkspaceFindingTier;
    chapter_index?: number;
    status?: string;
    product_dimension?: ProductDimension;
  },
): Promise<WorkspaceFinding[]> {
  const { data } = await client.get<WorkspaceFinding[]>(`/books/${bookId}/review-workspace/findings`, { params });
  return data;
}

export async function runReviewWorkspace(
  bookId: string,
  body: { scope: "book" | "chapter"; chapter_index?: number },
): Promise<{ task_id: string | null; run_id: string | null; status: string; message: string; summary_text?: string }> {
  const { data } = await client.post(`/books/${bookId}/review-workspace/run`, body);
  return data;
}

export async function runCustomReview(
  bookId: string,
  body: { prompt: string; chapter_index?: number },
): Promise<{ task_id: string | null; run_id: string | null; status: string; message: string; summary_text?: string }> {
  const { data } = await client.post(`/books/${bookId}/review-workspace/custom`, body);
  return data;
}

export async function patchReviewWorkspaceFinding(
  bookId: string,
  findingId: string,
  source: "chapter" | "book",
  status: string,
): Promise<WorkspaceFinding> {
  const { data } = await client.patch<WorkspaceFinding>(
    `/books/${bookId}/review-workspace/findings/${findingId}?source=${source}`,
    { status },
  );
  return data;
}

export async function recheckReviewWorkspaceFinding(bookId: string, findingId: string): Promise<WorkspaceFinding> {
  const { data } = await client.post<WorkspaceFinding>(
    `/books/${bookId}/review-workspace/findings/${findingId}/recheck`,
  );
  return data;
}

export async function getFindingHistory(
  bookId: string,
  findingId: string,
): Promise<Array<{ application_id: string; apply_type: string; created_at: string | null }>> {
  const { data } = await client.get(`/books/${bookId}/review-workspace/findings/${findingId}/history`);
  return data;
}

export async function applyReviewWorkspaceFinding(
  bookId: string,
  findingId: string,
  body?: { replacement_text?: string; action_type?: string },
): Promise<{
  issue_id: string;
  application_id: string;
  quote: string;
  result_text: string;
  result_markdown: string;
  preview_kind: string;
  preview_required: boolean;
  stale: boolean;
  char_start?: number;
  char_end?: number;
}> {
  const { data } = await client.post(`/books/${bookId}/review-workspace/findings/${findingId}/apply`, body ?? {});
  return data;
}
