import type { LiteratureSearchResult } from "@/types/literature";
import type { RightPanelTab } from "@/components/editor/RightPanel";

export type ToolResult = {
  name: string;
  ok: boolean;
  panel_hint: string;
  data: Record<string, unknown>;
  requires_confirmation?: boolean;
  error?: string | null;
};

export type PanelToolSeed = {
  literatureQuery?: string;
  literatureResult?: LiteratureSearchResult;
  reviewRunResult?: Record<string, unknown>;
  figureListSeed?: { chapter_index?: number; figures?: unknown[] };
  confirmationPreview?: { name: string; preview: string; instruction?: string };
  memoryRefresh?: boolean;
};

export function panelHintToTab(hint: string): RightPanelTab | null {
  switch (hint) {
    case "literature":
      return "literature";
    case "review":
    case "review_workspace":
      return null;
    case "refs":
      return "refs";
    case "memory":
      return null;
    case "ai":
      return "ai";
    case "detail":
    case "basis":
    case "sources":
    case "confirm":
      return "detail";
    default:
      return null;
  }
}

function literaturePayloadFromToolData(data: Record<string, unknown>): {
  query: string;
  result: LiteratureSearchResult;
} | null {
  // search_references wraps literature under data.result; search_literature is flat
  const nested = data.result && typeof data.result === "object" ? (data.result as Record<string, unknown>) : null;
  const src =
    nested && (Array.isArray(nested.papers) || Array.isArray(nested.items) || Array.isArray(nested.wiki))
      ? nested
      : data;
  const papers = (src.papers as LiteratureSearchResult["papers"]) ?? [];
  const github = (src.github as LiteratureSearchResult["github"]) ?? [];
  const wiki = (src.wiki as LiteratureSearchResult["wiki"]) ?? [];
  const official_docs = (src.official_docs as LiteratureSearchResult["official_docs"]) ?? [];
  const items = (src.items as LiteratureSearchResult["items"]) ?? [];
  if (!papers.length && !github.length && !wiki.length && !official_docs.length && !items.length) {
    return null;
  }
  return {
    query: String(src.query ?? data.raw_query ?? data.query ?? ""),
    result: {
      papers,
      github,
      wiki,
      official_docs,
      refined_queries: (src.refined_queries as string[]) ?? (data.queries as string[]) ?? [],
      warnings: (src.warnings as string[]) ?? [],
      items,
      profile: src.profile as string | undefined,
      source_hint: src.source_hint as string | undefined,
      books: (src.books as LiteratureSearchResult["books"]) ?? [],
      news: (src.news as LiteratureSearchResult["news"]) ?? [],
      government: (src.government as LiteratureSearchResult["government"]) ?? [],
      industry_reports: (src.industry_reports as LiteratureSearchResult["industry_reports"]) ?? [],
      technical: (src.technical as LiteratureSearchResult["technical"]) ?? [],
      web: (src.web as LiteratureSearchResult["web"]) ?? [],
      facets: (src.facets as LiteratureSearchResult["facets"]) ?? [],
      execution: src.execution as LiteratureSearchResult["execution"],
      plan: src.plan as LiteratureSearchResult["plan"],
    },
  };
}

export function buildSeedFromToolResults(results: ToolResult[]): PanelToolSeed {
  const seed: PanelToolSeed = {};
  for (const r of results) {
    if (!r.ok) continue;
    const data = r.data ?? {};
    if (r.panel_hint === "literature" || r.name === "search_references" || r.name === "search_sources" || r.name === "search_literature") {
      const lit = literaturePayloadFromToolData(data);
      if (lit) {
        seed.literatureQuery = lit.query;
        seed.literatureResult = lit.result;
      }
    }
    if (r.panel_hint === "review" || r.name === "run_review") {
      seed.reviewRunResult = data;
    }
    if (r.panel_hint === "refs" && r.name === "list_chapter_figures") {
      seed.figureListSeed = {
        chapter_index: data.chapter_index as number | undefined,
        figures: data.figures as unknown[],
      };
    }
    if (r.panel_hint === "memory" || r.name === "update_project_understanding") {
      seed.memoryRefresh = true;
    }
    if (r.requires_confirmation && r.panel_hint === "confirm") {
      seed.confirmationPreview = {
        name: r.name,
        preview: String(data.preview ?? ""),
        instruction: data.instruction as string | undefined,
      };
    }
  }
  return seed;
}

export function mergePanelSeed(prev: PanelToolSeed, next: PanelToolSeed): PanelToolSeed {
  return { ...prev, ...next };
}
