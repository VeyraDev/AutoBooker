import { client } from "@/api/client";

export type WorkspaceFindingTier = "must_fix" | "suggest" | "observe" | "needs_verification";

export type FindingFixCapability = "preview_apply" | "choice_then_apply" | "manual_only" | "observe_only";

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

export type ReviewActionOption = {
  id: string;
  label: string;
  description?: string;
  action_type?: string;
};

export type ReviewEvidenceItem = {
  type: string;
  label: string;
  detail: string;
  source?: string | null;
  examples?: string[];
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
  evidence_items?: ReviewEvidenceItem[];
  paragraph_id?: string | null;
  paragraph_index?: number | null;
  char_start?: number | null;
  char_end?: number | null;
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
  verification_status?: string | null;
  action_options?: ReviewActionOption[];
  fix_capability?: FindingFixCapability | null;
  prefer_evidence_binding?: boolean;
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
  needs_verification_count?: number;
  open_count: number;
  run_status: string | null;
  by_chapter: Record<string, number>;
  latest_task: ReviewTask | null;
};

export type ReviewRuleDecision = {
  id: string;
  candidate_id: string;
  version: number;
  status: "active" | "rejected" | "archived";
  recommendation: string;
  product_dimension: string;
  issue_type: string;
  fix_capability: string;
  detector: string;
  rule_text: string;
  decision_note: string;
  source_stats: Record<string, unknown>;
  created_at: string | null;
};

export type ReviewRuleCandidate = {
  id: string;
  status: "candidate";
  recommendation: "promote" | "demote";
  product_dimension: string;
  issue_type: string;
  fix_capability: string;
  detector: string;
  accepted: number;
  dismissed: number;
  open: number;
  decided: number;
  acceptance_rate: number;
  dismissal_rate: number;
  examples: string[];
  reason: string;
  safety_note: string;
  decision?: ReviewRuleDecision | null;
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

export async function listReviewRuleCandidates(
  bookId: string,
  includeDecided = false,
): Promise<ReviewRuleCandidate[]> {
  const { data } = await client.get<ReviewRuleCandidate[]>(`/books/${bookId}/review-workspace/rule-candidates`, {
    params: { include_decided: includeDecided },
  });
  return data;
}

export async function listConfirmedReviewRules(bookId: string): Promise<ReviewRuleDecision[]> {
  const { data } = await client.get<ReviewRuleDecision[]>(`/books/${bookId}/review-workspace/rules`);
  return data;
}

export async function listReviewRuleVersions(bookId: string, candidateId?: string): Promise<ReviewRuleDecision[]> {
  const { data } = await client.get<ReviewRuleDecision[]>(`/books/${bookId}/review-workspace/rules/history`, {
    params: candidateId ? { candidate_id: candidateId } : undefined,
  });
  return data;
}

export async function restoreReviewRuleVersion(
  bookId: string,
  ruleId: string,
  body?: { decision_note?: string },
): Promise<ReviewRuleDecision> {
  const { data } = await client.post<ReviewRuleDecision>(
    `/books/${bookId}/review-workspace/rules/${ruleId}/restore`,
    body ?? {},
  );
  return data;
}

export async function decideReviewRuleCandidate(
  bookId: string,
  candidateId: string,
  body: { decision: "active" | "rejected"; decision_note?: string; rule_text?: string },
): Promise<ReviewRuleDecision> {
  const { data } = await client.post<ReviewRuleDecision>(
    `/books/${bookId}/review-workspace/rule-candidates/decision`,
    body,
    { params: { candidate_id: candidateId } },
  );
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

export type WorkspaceFindingApplyResult = {
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
};

export async function applyReviewWorkspaceFinding(
  bookId: string,
  findingId: string,
  body?: { replacement_text?: string; action_type?: string; action_option_id?: string },
): Promise<WorkspaceFindingApplyResult> {
  const { data } = await client.post(`/books/${bookId}/review-workspace/findings/${findingId}/apply`, body ?? {});
  return data;
}

export async function batchPreviewReviewWorkspaceFindings(
  bookId: string,
  body: { finding_ids: string[]; limit?: number },
): Promise<{
  requested_count: number;
  previewed_count: number;
  skipped_count: number;
  items: WorkspaceFindingApplyResult[];
  skipped: Array<{ finding_id: string; reason: string; title?: string | null }>;
}> {
  const { data } = await client.post(`/books/${bookId}/review-workspace/findings/batch-preview`, body);
  return data;
}
