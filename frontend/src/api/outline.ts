import { client } from "@/api/client";
import type {
  OutlineBookResponse,
  OutlineGeneratePayload,
  OutlinePutPayload,
} from "@/types/outline";

export async function getOutline(bookId: string): Promise<OutlineBookResponse> {
  const { data } = await client.get<OutlineBookResponse>(`/books/${bookId}/outline`);
  return data;
}

/** Outline generation calls the LLM synchronously; default axios timeout (15s) is too short. */
const OUTLINE_GENERATE_TIMEOUT_MS = 180_000;

export async function generateOutline(
  bookId: string,
  payload?: OutlineGeneratePayload,
): Promise<OutlineBookResponse> {
  const { data } = await client.post<OutlineBookResponse>(
    `/books/${bookId}/outline`,
    payload ?? {},
    { timeout: OUTLINE_GENERATE_TIMEOUT_MS },
  );
  return data;
}

export async function putOutline(bookId: string, payload: OutlinePutPayload): Promise<OutlineBookResponse> {
  const { data } = await client.put<OutlineBookResponse>(`/books/${bookId}/outline`, payload);
  return data;
}
