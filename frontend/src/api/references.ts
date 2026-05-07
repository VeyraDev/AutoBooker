import { client } from "@/api/client";
import type { ReferenceFile, ReferenceSearchPayload } from "@/types/reference";

export async function listReferences(bookId: string): Promise<ReferenceFile[]> {
  const { data } = await client.get<ReferenceFile[]>(`/books/${bookId}/references`);
  return data;
}

export async function uploadReference(bookId: string, file: File): Promise<{ id: string }> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<{ id: string; filename: string; parse_status: string }>(
    `/books/${bookId}/references/upload`,
    form,
  );
  return data;
}

export async function searchReferences(bookId: string, payload: ReferenceSearchPayload): Promise<{ snippets: string[] }> {
  const { data } = await client.post<{ snippets: string[] }>(`/books/${bookId}/references/search`, payload);
  return data;
}
