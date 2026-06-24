import { client } from "@/api/client";
import type { ReferenceFile, ReferenceSearchHit, ReferenceSearchPayload } from "@/types/reference";

export async function listReferences(bookId: string): Promise<ReferenceFile[]> {
  const { data } = await client.get<ReferenceFile[]>(`/books/${bookId}/references`);
  return data;
}

export type UploadIngestHint = "auto" | "material" | "reference";

export async function uploadReference(
  bookId: string,
  file: File,
  ingestHint: UploadIngestHint = "auto",
  shareToLibrary = false,
): Promise<{ id: string }> {
  const form = new FormData();
  form.append("file", file);
  if (ingestHint !== "auto") {
    form.append("ingest_hint", ingestHint);
  }
  if (shareToLibrary) {
    form.append("share_to_library", "true");
  }
  const { data } = await client.post<{ id: string; filename: string; parse_status: string }>(
    `/books/${bookId}/references/upload`,
    form,
  );
  return data;
}

export async function deleteReference(bookId: string, fileId: string): Promise<void> {
  await client.delete(`/books/${bookId}/references/${fileId}`);
}

export async function searchReferences(
  bookId: string,
  payload: ReferenceSearchPayload,
): Promise<{ snippets: string[]; hits: ReferenceSearchHit[] }> {
  const { data } = await client.post<{ snippets: string[]; hits: ReferenceSearchHit[] }>(
    `/books/${bookId}/references/search`,
    payload,
  );
  return data;
}
