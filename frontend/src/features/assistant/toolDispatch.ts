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
      return "review";
    case "review_workspace":
      return "review";
    case "refs":
      return "refs";
    case "memory":
      return "memory";
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

export function buildSeedFromToolResults(results: ToolResult[]): PanelToolSeed {
  const seed: PanelToolSeed = {};
  for (const r of results) {
    if (!r.ok) continue;
    const data = r.data ?? {};
    if (r.panel_hint === "literature") {
      seed.literatureQuery = String(data.query ?? "");
      seed.literatureResult = {
        papers: (data.papers as LiteratureSearchResult["papers"]) ?? [],
        github: (data.github as LiteratureSearchResult["github"]) ?? [],
        wiki: (data.wiki as LiteratureSearchResult["wiki"]) ?? [],
        official_docs: (data.official_docs as LiteratureSearchResult["official_docs"]) ?? [],
        refined_queries: (data.refined_queries as string[]) ?? [],
        warnings: (data.warnings as string[]) ?? [],
        items: (data.items as LiteratureSearchResult["items"]) ?? [],
        profile: data.profile as string | undefined,
        source_hint: data.source_hint as string | undefined,
      };
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
