export interface LiteraturePaper {
  id?: string;
  title: string;
  year?: number | null;
  authors: string[];
  journal?: string;
  doi?: string;
  citations?: number;
  type?: string | null;
  source?: string | null;
  source_label?: string | null;
  url?: string;
  semantic_scholar_id?: string | null;
  external_id?: string | null;
  abstract_preview?: string | null;
  document_type?: string | null;
  publisher?: string | null;
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  quotable_snippet?: string | null;
  snippet?: string;
  published_at?: string | null;
  source_type?: SourceType;
  provider?: string;
  domain?: string;
  relevance?: number;
  credibility_hint?: "high" | "medium" | "unknown";
  citeability?: boolean;
  metadata_missing?: string[];
  isbn?: string;
  degraded?: boolean;
}

export type SourceType =
  | "paper"
  | "book"
  | "news"
  | "government"
  | "industry_report"
  | "technical"
  | "web";

export interface SourceCapability {
  id: SourceType;
  label: string;
  available: boolean;
  connectors: string[];
  unavailable_reason?: string | null;
}

export interface SourceFacet {
  id: SourceType;
  label: string;
  count: number;
}

export interface SourceSearchExecution {
  requested_source_types: SourceType[];
  attempted_connectors: string[];
  successful_connectors: string[];
  failed_connectors: Record<string, string>;
  unavailable_source_types: SourceType[];
  degraded: boolean;
  duration_ms: number;
  result_counts: Partial<Record<SourceType, number>>;
}

export interface LiteratureSearchResult {
  papers: LiteraturePaper[];
  github: LiteraturePaper[];
  wiki: LiteraturePaper[];
  official_docs: LiteraturePaper[];
  refined_queries: string[];
  warnings?: string[];
  items: LiteraturePaper[];
  profile?: string;
  source_hint?: string;
  books?: LiteraturePaper[];
  news?: LiteraturePaper[];
  government?: LiteraturePaper[];
  industry_reports?: LiteraturePaper[];
  technical?: LiteraturePaper[];
  web?: LiteraturePaper[];
  facets?: SourceFacet[];
  execution?: SourceSearchExecution;
  plan?: {
    scope?: "manual" | "book" | "chapter";
    chapter_index?: number | null;
    intent?: { kind?: string; display_query?: string; rationale?: string };
    requested_source_types?: SourceType[];
  };
}

export interface LiteratureRefineResult {
  refined_queries: string[];
  must_include: string[];
  must_exclude: string[];
}

export type LiteratureTab = "papers" | "github" | "wiki" | "official_docs";

export interface LiteratureQuoteBlock {
  citation_id: string;
  in_text_mark: string;
  quote_body: string;
  bibliography_line: string;
  fetch_status: string;
  source_label?: string;
  title?: string;
}

export function literaturePaperKey(p: LiteraturePaper): string {
  if (p.id) return p.id;
  if (p.external_id && p.source) return `${p.source}:${p.external_id}`.toLowerCase();
  if (p.doi?.trim()) return `doi:${p.doi.toLowerCase()}`;
  return (p.title || "").toLowerCase();
}

export function literaturePaperUrl(p: LiteraturePaper): string {
  if (p.url?.trim()) return p.url.trim();
  if (p.source === "wikipedia" && p.external_id) {
    return `https://zh.wikipedia.org/wiki/${encodeURIComponent(p.external_id.replace(/ /g, "_"))}`;
  }
  if (p.source === "arxiv" && p.external_id) {
    return `https://arxiv.org/abs/${p.external_id}`;
  }
  if (p.source === "github" && p.external_id) {
    return `https://github.com/${p.external_id}`;
  }
  if (p.source === "official_doc" && p.url?.trim()) {
    return p.url.trim();
  }
  if (p.doi?.trim()) return `https://doi.org/${p.doi.replace(/^https?:\/\/doi\.org\//i, "")}`;
  if (p.semantic_scholar_id?.trim()) {
    return `https://www.semanticscholar.org/paper/${p.semantic_scholar_id}`;
  }
  if (p.title?.trim()) {
    return `https://scholar.google.com/scholar?q=${encodeURIComponent(p.title)}`;
  }
  return "";
}

export interface CitationRecord {
  id: string;
  book_id: string;
  doi?: string | null;
  title: string;
  authors: string[];
  year?: number | null;
  journal?: string | null;
  format_cache?: Record<string, string> | null;
  source: "literature_search" | "uploaded_file" | "manual";
  source_file_id?: string | null;
  raw_text?: string | null;
  quotable_snippet?: string | null;
  abstract_preview?: string | null;
  url?: string | null;
  document_type?: string | null;
  publisher?: string | null;
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  metadata_status?: "complete" | "needs_completion";
  external_source?: string | null;
  list_index?: number | null;
  verification_status?: string | null;
  verification_result?: Record<string, unknown> | null;
  last_verified_at?: string | null;
  formatted?: string | null;
  created_at: string;
}

export interface CitationVerificationJob {
  id: string;
  book_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled" | string;
  requested_citation_ids?: string[] | null;
  total_count: number;
  processed_count: number;
  succeeded_count: number;
  failed_count: number;
  progress_pct: number;
  result_json?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at: string;
  finished_at?: string | null;
}

export interface CitationVerificationDueJobRequest {
  stale_after_days?: number;
  limit?: number;
  include_unverified?: boolean;
  retry_unreachable_only?: boolean;
}

export interface CitationVerificationDueJobResult {
  selected_count: number;
  skipped_reason?: "active_job_exists" | "no_due_citations" | string | null;
  job?: CitationVerificationJob | null;
}
