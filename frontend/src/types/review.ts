export type ReviewSeverity = "high" | "medium" | "low";
export type ReviewActionType = "replace" | "delete" | "insert" | "revise";
export type ReviewIssueStatus = "open" | "applied" | "resolved" | "dismissed" | "stale" | "failed";

export type ReviewCategory =
  | "logic"
  | "style"
  | "grammar"
  | "citation"
  | "structure"
  | "hallucination"
  | "figure"
  | "code"
  | "consistency"
  | "other";

export type ReviewDimensionKey =
  | "logic_structure"
  | "language_grammar"
  | "style_consistency"
  | "citation_sources"
  | "factual_support"
  | "figure_quality"
  | "ai_signature";

export interface ReviewIssue {
  id: string;
  severity: ReviewSeverity;
  category: ReviewCategory;
  title: string;
  detail: string;
  quote: string;
  suggestion: string;
  action_type?: ReviewActionType;
  paragraph_index?: number | null;
  char_offset?: number | null;
  dimension?: ReviewDimensionKey | string | null;
  issue_type?: string;
  penalty?: number;
  status?: ReviewIssueStatus;
  explanation?: string;
  action?: ReviewActionType;
  replacement_text?: string;
  paragraph_id?: string | null;
  char_start?: number | null;
  char_end?: number | null;
  anchor_hash?: string | null;
  issue_fingerprint?: string | null;
  detector?: string;
  confidence?: number;
  stale?: boolean;
}

export interface ReviewDimension {
  key?: ReviewDimensionKey | string | null;
  dimension?: ReviewDimensionKey | string | null;
  label?: string;
  weight?: number;
  raw_score?: number;
  effective_score?: number;
  score: number;
  issue_count?: number;
  summary?: string;
  detector?: string;
  confidence?: number;
  status?: string;
}

export interface ReviewApplyResult {
  issue_id?: string | null;
  application_id?: string | null;
  quote: string;
  result_text: string;
  result_markdown?: string | null;
  preview_kind: "replace" | "insert" | "delete";
  diff?: Record<string, unknown>;
  locator_strategy?: string;
  locator_confidence?: number;
  preview_required?: boolean;
  stale?: boolean;
  affected_dimensions?: string[];
  score_changes?: Array<Record<string, unknown>>;
  warning?: Record<string, unknown> | null;
  paragraph_id?: string | null;
  paragraph_index?: number | null;
  char_start?: number | null;
  char_end?: number | null;
}

export interface ReviewConfirmResult {
  application_id: string;
  issue_status?: ReviewIssueStatus | null;
  score?: number | null;
  dimensions?: ReviewDimension[];
}

export interface CitationLintIssue {
  kind: string;
  quote: string;
  detail: string;
  suggested_title?: string | null;
}

export interface ChapterReviewResult {
  chapter_index: number;
  chapter_title: string;
  summary: string;
  score: number;
  total_score?: number | null;
  dimensions?: Record<string, ReviewDimension>;
  dimension_rows?: ReviewDimension[];
  issues: ReviewIssue[];
  citation_issues?: CitationLintIssue[];
  word_count: number;
  review_id?: string | null;
  snapshot_hash?: string | null;
  snapshot_md?: string | null;
  status?: string;
  is_stale?: boolean;
  created_at?: string | null;
}

export interface ReviewHistoryItem {
  review_id: string;
  chapter_index: number;
  chapter_title: string;
  score: number;
  status: string;
  snapshot_hash: string;
  created_at: string;
  is_stale?: boolean;
  dimensions?: ReviewDimension[];
}

export interface AiInlinePreviewResult {
  preview_id: string;
  original_text: string;
  rewritten_text: string;
  diff?: Record<string, unknown>;
  validation?: Record<string, unknown>;
}

export const REVIEW_DIMENSION_LABEL: Record<ReviewDimensionKey, string> = {
  logic_structure: "逻辑结构",
  language_grammar: "语言语法",
  style_consistency: "风格一致",
  citation_sources: "引用来源",
  factual_support: "事实支撑",
  figure_quality: "图表质量",
  ai_signature: "AI味风险",
};

export const REVIEW_CATEGORY_LABEL: Record<ReviewCategory, string> = {
  logic: "逻辑",
  style: "文风",
  grammar: "语病",
  citation: "引用",
  structure: "结构",
  hallucination: "事实支撑",
  figure: "图表",
  code: "代码",
  consistency: "风格一致",
  other: "其他",
};

export const REVIEW_ACTION_LABEL: Record<ReviewActionType, string> = {
  replace: "替换",
  delete: "删除",
  insert: "新增",
  revise: "AI 改写",
};

export const REVIEW_SEVERITY_LABEL: Record<ReviewSeverity, string> = {
  high: "严重",
  medium: "中等",
  low: "轻微",
};

export const REVIEW_STATUS_LABEL: Record<ReviewIssueStatus, string> = {
  open: "待处理",
  applied: "已应用",
  resolved: "已解决",
  dismissed: "已忽略",
  stale: "旧版本",
  failed: "失败",
};
