export type ParseStatus = "pending" | "processing" | "done" | "failed";

export type FilePurpose = "outline" | "writing_requirements" | "reference";

export type OutlineUsage = "primary" | "reference";

export interface ReferenceFile {
  id: string;
  book_id: string;
  filename: string;
  file_type: string;
  ingest_kind?: string;
  file_purposes?: FilePurpose[] | null;
  outline_usage?: OutlineUsage | null;
  user_note?: string | null;
  parse_status: ParseStatus;
  error_message: string | null;
  parsed_at: string | null;
  created_at: string;
  chunk_count?: number;
}

export interface ReferenceSearchHit {
  content: string;
  filename: string;
}

export interface ReferenceSearchPayload {
  query: string;
  top_k?: number;
}

export interface UploadReferenceOptions {
  filePurposes?: FilePurpose[];
  outlineUsage?: OutlineUsage;
  userNote?: string;
  shareToLibrary?: boolean;
  /** @deprecated 兼容旧上传 */
  ingestHint?: "auto" | "material" | "reference";
}
