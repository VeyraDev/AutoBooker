import axios from "axios";

import { client } from "@/api/client";
import type { Book, BookCreatePayload, BookUpdatePayload, SetupRecommendResult } from "@/types/book";

export async function listBooks(): Promise<Book[]> {
  const { data } = await client.get<Book[]>("/books");
  return data;
}

export async function getBook(id: string): Promise<Book> {
  const { data } = await client.get<Book>(`/books/${id}`);
  return data;
}

export async function createBook(payload: BookCreatePayload): Promise<Book> {
  const { data } = await client.post<Book>("/books", payload);
  return data;
}

export async function updateBook(id: string, payload: BookUpdatePayload): Promise<Book> {
  const { data } = await client.put<Book>(`/books/${id}`, payload);
  return data;
}

/** 设定推荐会同步调用 LLM，默认 axios 超时（15s）过短。 */
const SETUP_RECOMMEND_TIMEOUT_MS = 120_000;

export async function setupRecommend(
  id: string,
  options?: { force?: boolean },
): Promise<SetupRecommendResult> {
  const { data } = await client.post<SetupRecommendResult>(
    `/books/${id}/setup-recommend`,
    { force: options?.force ?? false },
    { timeout: SETUP_RECOMMEND_TIMEOUT_MS },
  );
  return data;
}

export async function duplicateBook(
  id: string,
  options?: { copy_outline?: boolean },
): Promise<{ book: Book; message: string }> {
  const { data } = await client.post<{ book: Book; message: string }>(`/books/${id}/duplicate`, {
    copy_outline: options?.copy_outline ?? false,
  });
  return data;
}

export async function deleteBook(id: string): Promise<void> {
  await client.delete(`/books/${id}`);
}

export type ExportFormat = "markdown" | "docx" | "pdf";

export const EXPORT_EXT: Record<ExportFormat, string> = {
  markdown: "md",
  docx: "docx",
  pdf: "pdf",
};

export type PageFormatOption = {
  id: string;
  label: string;
  short_label: string;
  width_mm: number;
  height_mm: number;
  type_area_width_mm: number;
  type_area_height_mm: number;
  margin_top_mm?: number;
  margin_bottom_mm?: number;
  margin_inner_mm?: number;
  margin_outer_mm?: number;
  margins_text?: string;
  binding_type?: string;
  body_pt: number;
  group: string;
  hint: string;
  aka: string;
  size_text: string;
};

export type PublicationInfo = {
  title?: string;
  subtitle?: string;
  author?: string;
  publisher?: string;
  publish_year?: string;
  isbn?: string;
  edition?: string;
  series?: string;
  cip_text?: string;
  price?: string;
  editor?: string;
  proofreader?: string;
  address?: string;
  postal_code?: string;
  print_count?: string;
  word_count_label?: string;
  format_label?: string;
  page_format_id?: string;
  /** paperback=平装 | hardcover=精装 */
  binding_type?: string;
  cover_layout?: Record<string, { x: number; y: number }>;
  cover_theme?: string;
  cover_bg_seed?: string;
  /** 智灵 gpt-image-2 生成的封面背景 binary_asset id */
  cover_bg_asset_id?: string;
};

export type ExportPreview = {
  publication_info: PublicationInfo;
  preface_enabled: boolean;
  preface_title: string;
  preface_html: string;
  toc: Array<{
    title: string;
    section_type: string;
    chapter_index?: number | null;
    level?: number;
    page?: number | null;
  }>;
  chapters: Array<{ index: number; title: string; html: string }>;
  bibliography_title: string | null;
  bibliography_html: string;
  preview_html: string;
  cover_image_data_url?: string;
  page_format?: {
    id?: string;
    label?: string;
    short_label?: string;
    width_mm?: number;
    height_mm?: number;
    margin_top_mm?: number;
    margin_bottom_mm?: number;
    margin_inner_mm?: number;
    margin_outer_mm?: number;
    type_area_width_mm?: number;
    type_area_height_mm?: number;
    margins_text?: string;
    binding_type?: string;
    hint?: string;
    aka?: string;
  };
  page_format_options?: PageFormatOption[];
};

async function blobErrorMessage(blob: Blob): Promise<string> {
  const text = await blob.text();
  let msg = "导出失败";
  try {
    const j = JSON.parse(text) as { detail?: string | Array<{ msg?: string }> };
    if (typeof j.detail === "string") msg = j.detail;
    else if (Array.isArray(j.detail))
      msg =
        j.detail
          .map((x) => (x && typeof x === "object" && "msg" in x ? String(x.msg) : ""))
          .filter(Boolean)
          .join("; ") || msg;
  } catch {
    msg = text.slice(0, 200);
  }
  return msg;
}

export async function fetchExportNotice(id: string): Promise<{ suggestions: string[] }> {
  const { data } = await client.get<{ message?: string | null; suggestion_count?: number }>(`/books/${id}/export/notice`);
  const suggestions: string[] = [];
  if (data.message) suggestions.push(data.message);
  return { suggestions };
}

export async function fetchExportPreview(id: string): Promise<ExportPreview> {
  const { data } = await client.get<ExportPreview>(`/books/${id}/export/preview`, { timeout: 120000 });
  return data;
}

export async function refreshExportPreview(
  id: string,
  payload: {
    publication_info?: PublicationInfo;
    persist?: boolean;
    regenerate_cover_bg?: boolean;
  },
): Promise<ExportPreview> {
  const timeout = payload.regenerate_cover_bg ? 180000 : 120000;
  const { data } = await client.post<ExportPreview>(`/books/${id}/export/preview`, payload, { timeout });
  return data;
}

/** 下载二进制；若服务端返回 JSON 错误体会抛出 Error */
export async function exportBook(id: string, format: ExportFormat): Promise<Blob> {
  try {
    const res = await client.get(`/books/${id}/export`, {
      params: { format },
      responseType: "blob",
      timeout: 120000,
    });
    const ct = String(res.headers["content-type"] ?? "");
    if (ct.includes("application/json")) {
      throw new Error(await blobErrorMessage(res.data as Blob));
    }
    return res.data as Blob;
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.data instanceof Blob) {
      const ct = String(e.response.headers["content-type"] ?? "");
      if (ct.includes("application/json")) {
        throw new Error(await blobErrorMessage(e.response.data));
      }
    }
    throw e;
  }
}
