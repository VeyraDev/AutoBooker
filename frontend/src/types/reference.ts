export type ParseStatus = "pending" | "processing" | "done" | "failed";

export interface ReferenceFile {
  id: string;
  book_id: string;
  filename: string;
  file_type: string;
  parse_status: ParseStatus;
  error_message: string | null;
  parsed_at: string | null;
  created_at: string;
}

export interface ReferenceSearchPayload {
  query: string;
  top_k?: number;
}
