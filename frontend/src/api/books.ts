import axios from "axios";

import { client } from "@/api/client";
import type { Book, BookCreatePayload, BookUpdatePayload } from "@/types/book";

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

export async function deleteBook(id: string): Promise<void> {
  await client.delete(`/books/${id}`);
}

export type ExportFormat = "markdown" | "docx";

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

/** 下载二进制；若服务端返回 JSON 错误体会抛出 Error */
export async function exportBook(id: string, format: ExportFormat): Promise<Blob> {
  const query = format === "markdown" ? "markdown" : "docx";
  try {
    const res = await client.get(`/books/${id}/export`, {
      params: { format: query },
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
