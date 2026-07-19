import { client } from "./client";

export interface GlobalLiteratureItem {
  id: string;
  source: string;
  title: string;
  authors: string[];
  year?: number | null;
  journal?: string | null;
  doi?: string | null;
  url?: string | null;
  abstract?: string | null;
  tags: string[];
  contributor_name?: string | null;
  cite_count: number;
}

export interface LibraryCategory {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  sort_order: number;
}

export interface LibraryShelfItem {
  id: string;
  title: string;
  authors: string[];
  description?: string | null;
  category_id?: string | null;
  category_slug?: string | null;
  category_name?: string | null;
  tags: string[];
  language?: string | null;
  file_type: string;
  filename: string;
  size_bytes: number;
  uploader_name?: string | null;
  use_count: number;
  created_at?: string | null;
  is_mine?: boolean;
}

export async function listGlobalLibrary(params?: {
  source?: string;
  tag?: string;
  q?: string;
  mine?: boolean;
}): Promise<{ items: GlobalLiteratureItem[]; total: number }> {
  const { data } = await client.get("/library", { params });
  return data;
}

export async function addLibraryToBook(bookId: string, literatureId: string): Promise<void> {
  await client.post(`/library/books/${bookId}/add`, { literature_id: literatureId });
}

export async function listShelfCategories(): Promise<LibraryCategory[]> {
  const { data } = await client.get<LibraryCategory[]>("/library/shelf/categories");
  return data;
}

export async function listShelfItems(params?: {
  category?: string;
  q?: string;
  mine?: boolean;
  limit?: number;
  offset?: number;
}): Promise<{ items: LibraryShelfItem[]; total: number; categories: LibraryCategory[] }> {
  const { data } = await client.get("/library/shelf", { params });
  return data;
}

export async function uploadShelfItem(form: {
  file: File;
  title: string;
  authors: string[];
  description: string;
  category_slug: string;
  tags: string[];
}): Promise<LibraryShelfItem> {
  const body = new FormData();
  body.append("file", form.file);
  body.append("title", form.title);
  body.append("authors", JSON.stringify(form.authors));
  body.append("description", form.description);
  body.append("category_slug", form.category_slug);
  body.append("tags", JSON.stringify(form.tags));
  const { data } = await client.post<{ item: LibraryShelfItem }>("/library/shelf/upload", body, {
    timeout: 180000,
  });
  return data.item;
}

export async function addShelfItemToBook(bookId: string, itemId: string): Promise<{ reference_file_id: string }> {
  const { data } = await client.post<{ ok: boolean; reference_file_id: string }>(
    `/library/shelf/books/${bookId}/add`,
    { item_id: itemId },
    { timeout: 120000 },
  );
  return data;
}

/** 下载共享书架文件为浏览器 File，便于走既有上传接口 */
export async function fetchShelfItemAsFile(item: Pick<LibraryShelfItem, "id" | "filename" | "file_type">): Promise<File> {
  const res = await client.get<Blob>(`/library/shelf/${item.id}/content`, {
    responseType: "blob",
    timeout: 180000,
  });
  const mime =
    res.headers["content-type"] ||
    (item.file_type === "pdf"
      ? "application/pdf"
      : item.file_type === "docx"
        ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        : "text/plain");
  return new File([res.data], item.filename || `shelf-${item.id}.${item.file_type}`, { type: mime });
}
