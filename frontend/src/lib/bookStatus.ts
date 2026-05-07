import type { Book, BookStatus } from "@/types/book";

export type Phase = "SETUP" | "WRITING" | "COMPLETED";

export function phaseOf(book: Book): Phase {
  if (book.status === "completed") return "COMPLETED";
  if (book.status === "writing" || book.status === "review_ready") return "WRITING";
  return "SETUP";
}

export type OutlineUiState = "idle" | "generating" | "ready";

export function outlineState(book: Book, hasChapters: boolean): OutlineUiState {
  if (book.status === "outline_generating") return "generating";
  if (book.status === "outline_ready" || hasChapters) return "ready";
  return "idle";
}

/** True after user confirmed outline (backend moved to writing+). */
export function outlineConfirmed(book: Book): boolean {
  return (
    book.status === "writing" ||
    book.status === "review_ready" ||
    book.status === "completed"
  );
}

export function statusLabelBackend(s: BookStatus): string {
  const map: Record<BookStatus, string> = {
    setup: "设定中",
    outline_generating: "大纲生成中",
    outline_ready: "大纲就绪",
    writing: "写作中",
    review_ready: "待审校",
    completed: "已完成",
  };
  return map[s];
}
