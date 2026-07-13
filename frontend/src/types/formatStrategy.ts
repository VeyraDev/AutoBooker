export type ColumnSuggestion = {
  column_name: string;
  purpose?: string;
  appearance_condition?: string;
  required?: boolean;
  default_position?: string;
  forbidden_usage?: string;
};

export type FormatStrategy = {
  id: string;
  book_id: string;
  version: number;
  status: "draft" | "confirmed" | "superseded" | string;
  book_level_columns: ColumnSuggestion[];
  conditional_columns: ColumnSuggestion[];
  forbidden_patterns: string[];
  chapter_suggestions: Record<string, ColumnSuggestion[]>;
  created_at?: string;
  updated_at?: string | null;
};
