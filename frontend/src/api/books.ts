import { client } from "@/api/client";
import type { Book, BookCreatePayload } from "@/types/book";

export async function listBooks(): Promise<Book[]> {
  const { data } = await client.get<Book[]>("/books");
  return data;
}

export async function createBook(payload: BookCreatePayload): Promise<Book> {
  const { data } = await client.post<Book>("/books", payload);
  return data;
}

export async function deleteBook(id: string): Promise<void> {
  await client.delete(`/books/${id}`);
}
