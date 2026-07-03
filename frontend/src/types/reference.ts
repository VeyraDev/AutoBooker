export type ParseStatus = "pending" | "processing" | "done" | "failed";

export type FilePurpose =
  | "outline"
  | "writing_requirements"
  | "reference_material"
  | "bibliography"
  | "source_manuscript";

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
  lifecycle_status?: "processing" | "pending_confirmation" | "effective" | "disabled" | "failed";
  parse_artifacts?: {
    purposes?: string[];
    outline_candidate?: Array<{ title: string; sections?: unknown[] }>;
    writing_rules?: Array<string | Record<string, unknown>>;
    terminology?: Array<{ term: string; definition?: string }>;
    reference_chunk_count?: number;
    bibliography_count?: number;
    pending_issues?: unknown[];
  } | null;
  conflicts?: Array<{
    id: string;
    type: string;
    message: string;
    details?: Record<string, unknown> | null;
  }> | null;
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
