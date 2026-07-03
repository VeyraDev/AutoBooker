import { client } from "@/api/client";
import type {
  ReferenceFile,
  ReferenceSearchHit,
  ReferenceSearchPayload,
  UploadReferenceOptions,
} from "@/types/reference";

export async function listReferences(bookId: string): Promise<ReferenceFile[]> {
  const { data } = await client.get<ReferenceFile[]>(`/books/${bookId}/references`);
  return data;
}

export type UploadIngestHint = "auto" | "material" | "reference";

export async function uploadReference(
  bookId: string,
  file: File,
  options: UploadReferenceOptions | UploadIngestHint = "auto",
  shareToLibraryLegacy = false,
): Promise<{ id: string }> {
  const form = new FormData();
  form.append("file", file);

  const opts: UploadReferenceOptions =
    typeof options === "string" ? { ingestHint: options, shareToLibrary: shareToLibraryLegacy } : options;

  if (opts.ingestHint && opts.ingestHint !== "auto") {
    form.append("ingest_hint", opts.ingestHint);
  }
  if (opts.filePurposes?.length) {
    form.append("file_purposes", JSON.stringify(opts.filePurposes));
  }
  if (opts.outlineUsage) {
    form.append("outline_usage", opts.outlineUsage);
  }
  if (opts.userNote?.trim()) {
    form.append("user_note", opts.userNote.trim());
  }
  if (opts.shareToLibrary) {
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

export async function confirmReference(
  bookId: string,
  fileId: string,
  payload: {
    purposes?: string[];
    primary_outline?: boolean;
    conflict_resolutions?: Record<string, string>;
  },
): Promise<ReferenceFile> {
  const { data } = await client.patch<ReferenceFile>(
    `/books/${bookId}/references/${fileId}/confirm`,
    payload,
  );
  return data;
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
