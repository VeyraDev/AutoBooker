import type { BookType, StyleType } from "@/types/book";

export const STYLE_LABELS: Record<StyleType, string> = {
  popular_science: "入门科普型",
  practical_guide: "实战操作型",
  reference_tool: "工具手册型",
  insight_opinion: "观念洞察型",
  textbook: "教科书型",
  technical_deep_dive: "技术深度分析型",
  ai_review_commentary: "AI能力评估/评论型",
};

export const NONFICTION_STYLE_OPTIONS: { value: StyleType; label: string }[] = [
  { value: "popular_science", label: STYLE_LABELS.popular_science },
  { value: "practical_guide", label: STYLE_LABELS.practical_guide },
  { value: "reference_tool", label: STYLE_LABELS.reference_tool },
  { value: "insight_opinion", label: STYLE_LABELS.insight_opinion },
];

export const ACADEMIC_STYLE_OPTIONS: { value: StyleType; label: string }[] = [
  { value: "textbook", label: STYLE_LABELS.textbook },
  { value: "technical_deep_dive", label: STYLE_LABELS.technical_deep_dive },
  { value: "ai_review_commentary", label: STYLE_LABELS.ai_review_commentary },
];

export function styleOptionsFor(bookType: BookType): { value: StyleType; label: string }[] {
  return bookType === "academic" ? ACADEMIC_STYLE_OPTIONS : NONFICTION_STYLE_OPTIONS;
}

export const DEFAULT_TARGET_WORDS: Record<BookType, number> = {
  nonfiction: 80_000,
  academic: 200_000,
};

export const TOPIC_TAG_PRESETS: string[] = [
  "AI Agent",
  "OpenClaw",
  "AI编程",
  "一人公司",
  "AI教育",
  "LLM",
  "AI创业",
  "AI哲学",
  "短视频",
  "Coze",
  "RAG",
  "MCP",
];
