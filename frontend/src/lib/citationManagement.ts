import type { CitationStyle } from "@/types/book";

export const CITATION_MANAGEMENT_VIEWS = [
  ["search", "资料搜索"],
  ["manage", "引用管理"],
] as const;

export function citationSequenceLabel(
  style: CitationStyle | null,
  listIndex: number | null | undefined,
): string {
  return style === "gb_t7714" && listIndex != null ? `[${listIndex}] ` : "";
}
