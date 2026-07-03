export type BookType = "nonfiction" | "academic";
export type BookWorkflowMode = "from_scratch" | "optimize_existing";

export type BookStatus =
  | "setup"
  | "outline_generating"
  | "outline_ready"
  | "auto_generating"
  | "writing"
  | "review_ready"
  | "completed";

/** Backend chapter row status (generation pipeline). */
export type ChapterGenStatus = "pending" | "generating" | "done";

export type CitationStyle = "apa" | "mla" | "chicago" | "gb_t7714";

/** 二级体裁，与后端 StyleType 一致 */
export type StyleType =
  | "popular_science"
  | "practical_guide"
  | "reference_tool"
  | "insight_opinion"
  | "textbook"
  | "technical_deep_dive"
  | "ai_review_commentary";

export interface Book {
  id: string;
  user_id: string;
  title: string;
  workflow_mode: BookWorkflowMode;
  original_title?: string | null;
  allow_title_optimization?: boolean;
  cover_url?: string | null;
  book_type: BookType;
  discipline: string | null;
  disciplines?: string[] | null;
  target_audience?: string | null;
  citation_style: CitationStyle | null;
  target_words: number | null;
  status: BookStatus;
  style_type: StyleType | null;
  topic_tags: string[] | null;
  topic_brief?: string | null;
  user_material?: string | null;
  constitution_stale?: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface BookCreatePayload {
  title: string;
  book_type: BookType;
  discipline?: string | null;
  target_audience?: string | null;
  citation_style?: CitationStyle | null;
  target_words?: number;
  style_type?: StyleType | null;
  topic_tags?: string[] | null;
  workflow_mode?: BookWorkflowMode;
}

export interface BookUpdatePayload {
  title?: string;
  discipline?: string | null;
  disciplines?: string[] | null;
  target_audience?: string | null;
  citation_style?: CitationStyle | null;
  target_words?: number | null;
  status?: BookStatus;
  style_type?: StyleType | null;
  topic_tags?: string[] | null;
  topic_brief?: string | null;
  allow_title_optimization?: boolean;
}

export interface SetupRecommendResult {
  from_cache: boolean;
  cache_key: string;
  recommended_tags: string[];
  target_audience: string;
  disciplines: string[];
  topic_brief: string;
}
