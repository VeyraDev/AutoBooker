export type BookType = "nonfiction" | "academic";

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
  cover_url?: string | null;
  book_type: BookType;
  discipline: string | null;
  target_audience?: string | null;
  citation_style: CitationStyle | null;
  target_words: number | null;
  status: BookStatus;
  ai_model: string | null;
  style_type: StyleType | null;
  topic_tags: string[] | null;
  user_material?: string | null;
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
  ai_model?: string | null;
}

export interface BookUpdatePayload {
  title?: string;
  discipline?: string | null;
  target_audience?: string | null;
  citation_style?: CitationStyle | null;
  target_words?: number | null;
  status?: BookStatus;
  ai_model?: string | null;
  style_type?: StyleType | null;
  topic_tags?: string[] | null;
  user_material?: string | null;
}
