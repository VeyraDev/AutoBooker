import { client } from "@/api/client";

export type FigureType = "flowchart" | "chart" | "figure" | "screenshot";
export type FigureStatus = "pending" | "generated" | "uploaded" | "approved";

export type FigureQualityReport = {
  status?: string;
  warnings?: string[];
  failures?: string[];
  recommendations?: string[];
};

export type FigureListItem = {
  id: string;
  figure_number: string | null;
  type: FigureType;
  status: FigureStatus;
  caption: string | null;
  chapter: number;
  position_hint: string | null;
  file_url: string | null;
  svg_url: string | null;
  raw_annotation: string | null;
  quality_report?: FigureQualityReport | null;
};

export type FigureOut = {
  id: string;
  book_id: string;
  chapter_index: number;
  figure_number: string | null;
  figure_type: FigureType;
  status: FigureStatus;
  caption: string | null;
  raw_annotation: string | null;
  file_url: string | null;
  svg_url: string | null;
  position_hint: string | null;
  sort_order: number | null;
  updated_at?: string | null;
  quality_report?: FigureQualityReport | null;
};

export function figureGenerationToast(_qr?: FigureQualityReport | null): {
  kind: "success";
  message: string;
} {
  return { kind: "success", message: "图表已生成" };
}

/** 从 API 时间戳或本地毫秒时间生成缓存破坏参数 */
export function figureFileVersion(updatedAt?: string | null, localMs?: number): number {
  if (updatedAt) {
    const t = Date.parse(updatedAt);
    if (!Number.isNaN(t)) return t;
  }
  return localMs ?? Date.now();
}

export function resolveFigureUrl(
  fileUrl: string | null | undefined,
  fileVersion?: number | string | null,
): string {
  if (!fileUrl) return "";
  let url = fileUrl;
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    const path = url.startsWith("/") ? url : `/${url}`;
    const base = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
    url = base ? `${base}${path}` : path;
  }
  const v = fileVersion != null && String(fileVersion) !== "" ? String(fileVersion) : "";
  if (!v) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${encodeURIComponent(v)}`;
}

export function formatFigureLabel(figureNumber: string | null | undefined, isTable = false): string {
  if (!figureNumber) return isTable ? "表" : "图";
  const parts = figureNumber.split("-");
  if (parts.length >= 2) {
    const prefix = isTable ? "表" : "图";
    return `${prefix} ${parts[0]}-${parts[1]}`;
  }
  return isTable ? `表 ${figureNumber}` : `图 ${figureNumber}`;
}

/** 图解用短文案，避免把整段生成描述铺在图下 */
export function shortenFigureCaption(text: string | null | undefined, maxLen = 120): string {
  const t = (text ?? "").trim();
  if (!t) return "";
  const first = t.split(/[。！？\n]/)[0]?.trim() ?? t;
  const base = first.length >= 20 ? first : t;
  if (base.length <= maxLen) return base;
  return `${base.slice(0, maxLen).trim()}…`;
}

export async function listFigures(bookId: string) {
  const { data } = await client.get<{ items: FigureListItem[] }>(`/books/${bookId}/figures`);
  return data.items;
}

export async function getFigure(bookId: string, figureId: string) {
  const { data } = await client.get<FigureOut>(`/books/${bookId}/figures/${figureId}`);
  return data;
}

/** 图像/流程图生成含 LLM 与外部 API，耗时可能超过默认 15s */
const FIGURE_GENERATE_TIMEOUT_MS = 300_000;
/** 一键排序会对每张图/表串行调用 LLM 生成题注 */
const FIGURE_NORMALIZE_SORT_TIMEOUT_MS = 300_000;

export async function generateFigure(
  bookId: string,
  figureId: string,
  opts?: { chart_type?: string; sub_kind?: string },
) {
  const { data } = await client.post<FigureOut>(
    `/books/${bookId}/figures/${figureId}/generate`,
    opts ?? {},
    { timeout: FIGURE_GENERATE_TIMEOUT_MS },
  );
  return data;
}

export async function uploadFigure(bookId: string, figureId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<FigureOut>(`/books/${bookId}/figures/${figureId}/upload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  });
  return data;
}

export async function approveFigure(bookId: string, figureId: string) {
  const { data } = await client.patch<FigureOut>(`/books/${bookId}/figures/${figureId}/approve`);
  return data;
}

export async function updateFigureCaption(bookId: string, figureId: string, caption: string) {
  const { data } = await client.patch<FigureOut>(`/books/${bookId}/figures/${figureId}/caption`, { caption });
  return data;
}

export async function syncChapterFigures(bookId: string, chapterIndex: number) {
  const { data } = await client.post<{ tiptap_json: Record<string, unknown> }>(
    `/books/${bookId}/chapters/${chapterIndex}/figures/sync`,
  );
  return data.tiptap_json;
}

export async function refreshChapterFigures(
  bookId: string,
  chapterIndex: number,
  tiptapJson?: Record<string, unknown>,
) {
  const { data } = await client.post<{ items: FigureOut[] }>(
    `/books/${bookId}/chapters/${chapterIndex}/figures/refresh`,
    tiptapJson ? { tiptap_json: tiptapJson } : undefined,
  );
  return data.items;
}

export type FigureTableOverviewItem = {
  kind: "figure" | "table" | string;
  seq: number;
  number: string;
  label: string;
  title: string;
  has_reference: boolean;
  has_caption: boolean;
  figure_id: string | null;
  status: string | null;
};

export async function rebuildChapterBodyFromFigures(bookId: string, chapterIndex: number) {
  const { data } = await client.post<{
    tiptap_json: Record<string, unknown>;
    text: string;
    overview: FigureTableOverviewItem[];
  }>(`/books/${bookId}/chapters/${chapterIndex}/figures/rebuild-body`);
  return data;
}

export async function normalizeChapterFiguresTables(
  bookId: string,
  chapterIndex: number,
  tiptapJson: Record<string, unknown>,
) {
  const { data } = await client.post<{
    tiptap_json: Record<string, unknown>;
    text: string;
    overview: FigureTableOverviewItem[];
  }>(`/books/${bookId}/chapters/${chapterIndex}/figures/normalize-sort`, {
    tiptap_json: tiptapJson,
  }, { timeout: FIGURE_NORMALIZE_SORT_TIMEOUT_MS });
  return data;
}

export async function patchChapterOverviewCaptions(
  bookId: string,
  chapterIndex: number,
  payload: { tiptap_json: Record<string, unknown>; overview: FigureTableOverviewItem[] },
) {
  const { data } = await client.patch<{
    tiptap_json: Record<string, unknown>;
    text: string;
    overview: FigureTableOverviewItem[];
  }>(`/books/${bookId}/chapters/${chapterIndex}/figures/overview-captions`, payload);
  return data;
}
