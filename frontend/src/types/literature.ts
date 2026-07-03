export interface LiteraturePaper {
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
  formatted?: string | null;
  created_at: string;
}
