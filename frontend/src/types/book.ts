export type BookType = "nonfiction" | "academic";

export type BookStatus =
  | "setup"
  | "outline_generating"
  | "outline_ready"
  | "writing"
  | "review_ready"
  | "completed";

/** Backend chapter row status (generation pipeline). */
export type ChapterGenStatus = "pending" | "generating" | "done";

export type CitationStyle = "apa" | "mla" | "chicago" | "gb_t7714";

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
}

export interface BookUpdatePayload {
  title?: string;
  discipline?: string | null;
  target_audience?: string | null;
  citation_style?: CitationStyle | null;
  target_words?: number | null;
  status?: BookStatus;
  ai_model?: string | null;
}
