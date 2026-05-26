export type ReviewSeverity = "high" | "medium" | "low";
export type ReviewCategory = "logic" | "style" | "grammar" | "citation" | "structure" | "other";

export interface ReviewIssue {
  id: string;
  severity: ReviewSeverity;
  category: ReviewCategory;
  title: string;
  detail: string;
  quote: string;
  suggestion: string;
}

export interface ChapterReviewResult {
  chapter_index: number;
  chapter_title: string;
  summary: string;
  score: number;
  issues: ReviewIssue[];
  word_count: number;
}

export const REVIEW_CATEGORY_LABEL: Record<ReviewCategory, string> = {
  logic: "逻辑",
  style: "文风",
  grammar: "语病",
  citation: "引用",
  structure: "结构",
  other: "其他",
};

export const REVIEW_SEVERITY_LABEL: Record<ReviewSeverity, string> = {
  high: "严重",
  medium: "中等",
  low: "轻微",
};
