import { client } from "@/api/client";
import type { FormatStrategy } from "@/types/formatStrategy";

export async function getFormatStrategy(bookId: string): Promise<FormatStrategy> {
  const { data } = await client.get<FormatStrategy>(`/books/${bookId}/format-strategy`);
  return data;
}

export async function generateFormatStrategy(bookId: string, force = false): Promise<FormatStrategy> {
  const { data } = await client.post<FormatStrategy>(`/books/${bookId}/format-strategy/generate`, { force });
  return data;
}

export async function patchFormatStrategy(
  bookId: string,
  patch: Partial<Pick<FormatStrategy, "book_level_columns" | "conditional_columns" | "forbidden_patterns" | "chapter_suggestions">>,
): Promise<FormatStrategy> {
  const { data } = await client.patch<FormatStrategy>(`/books/${bookId}/format-strategy`, patch);
  return data;
}

export async function confirmFormatStrategy(bookId: string): Promise<{ strategy_id: string; status: string }> {
  const { data } = await client.post<{ strategy_id: string; status: string }>(
    `/books/${bookId}/format-strategy/confirm`,
  );
  return data;
}
