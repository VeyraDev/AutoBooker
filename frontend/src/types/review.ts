export type ReviewSeverity = "high" | "medium" | "low";
export type ReviewActionType = "replace" | "delete" | "insert" | "revise";

export type ReviewCategory =
  | "logic"
  | "style"
  | "grammar"
  | "citation"
  | "structure"
  | "hallucination"
  | "figure"
  | "other";

export interface ReviewIssue {
  id: string;
  severity: ReviewSeverity;
  category: ReviewCategory;
  title: string;
  detail: string;
  quote: string;
  suggestion: string;
  action_type?: ReviewActionType;
}

export interface ReviewApplyResult {
  quote: string;
  result_text: string;
  preview_kind: "replace" | "insert" | "delete";
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
  issues: ReviewIssue[];
  citation_issues?: CitationLintIssue[];
  word_count: number;
}

export const REVIEW_CATEGORY_LABEL: Record<ReviewCategory, string> = {
  logic: "逻辑",
  style: "文风",
  grammar: "语病",
  citation: "引用",
  structure: "结构",
  hallucination: "幻觉/无来源",
  figure: "图表",
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
