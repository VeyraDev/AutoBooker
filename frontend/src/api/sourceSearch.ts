import { client } from "@/api/client";
import type {
  CitationRecord,
  LiteraturePaper,
  LiteratureSearchResult,
  SourceCapability,
  SourceType,
} from "@/types/literature";

export async function listSourceSearchCapabilities(bookId: string): Promise<SourceCapability[]> {
  const { data } = await client.get<SourceCapability[]>(`/books/${bookId}/sources/search-capabilities`);
  return data;
}

export async function searchSources(
  bookId: string,
  opts: {
    query: string;
    rows?: number;
    scope?: "manual" | "book" | "chapter";
    chapterIndex?: number;
    sourceTypes?: SourceType[];
    signal?: AbortSignal;
  },
): Promise<LiteratureSearchResult> {
  const { data } = await client.post<LiteratureSearchResult>(
    `/books/${bookId}/sources/search`,
    {
      query: opts.query,
      rows: opts.rows ?? 25,
      scope: opts.scope ?? "manual",
      chapter_index: opts.chapterIndex,
      requested_source_types: opts.sourceTypes ?? [],
    },
    { timeout: 35000, signal: opts.signal },
  );
  return data;
}

export async function addSourceSearchResults(
  bookId: string,
  target: "source_library" | "citation_library",
  items: LiteraturePaper[],
): Promise<{
  target: typeof target;
  added_count: number;
  sources: unknown[];
  citations: CitationRecord[];
  rejected: Array<{ id?: string; title?: string; reason: string; metadata_missing?: string[] }>;
}> {
  const { data } = await client.post(`/books/${bookId}/sources/search-results/add`, {
    target,
    items: items.map((item) => ({
      id: item.id ?? literatureItemId(item),
      title: item.title,
      url: item.url ?? "",
      snippet: item.snippet ?? item.abstract_preview ?? "",
      authors: item.authors ?? [],
      publisher: item.publisher ?? item.journal ?? "",
      published_at: item.published_at ?? null,
      year: item.year ?? null,
      source_type: item.source_type ?? "web",
      provider: item.provider ?? item.source ?? "unknown",
      domain: item.domain ?? "",
      relevance: item.relevance ?? 0,
      credibility_hint: item.credibility_hint ?? "unknown",
      citeability: item.citeability ?? false,
      metadata_missing: item.metadata_missing ?? [],
      document_type: item.document_type ?? item.type ?? "",
      doi: item.doi ?? "",
      isbn: item.isbn ?? "",
      external_id: item.external_id ?? "",
      journal: item.journal ?? "",
      citations: item.citations ?? null,
      degraded: item.degraded ?? false,
    })),
  });
  return data;
}

function literatureItemId(item: LiteraturePaper): string {
  return `${item.provider ?? item.source ?? "source"}:${item.external_id ?? item.url ?? item.title}`;
}
