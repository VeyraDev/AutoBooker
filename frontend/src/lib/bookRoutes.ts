import type { Book } from "@/types/book";

export function autoBookProgressPath(bookId: string): string {
  return `/app/books/${bookId}/auto-progress`;
}

export function bookDestination(
  book: Pick<Book, "id" | "workflow_mode" | "status">,
): string {
  if (book.workflow_mode === "optimize_existing") {
    return `/app/books/${book.id}/optimize`;
  }
  if (book.status === "auto_generating") {
    return autoBookProgressPath(book.id);
  }
  return `/app/books/${book.id}`;
}
