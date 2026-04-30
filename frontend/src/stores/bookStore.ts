import { create } from "zustand";

import type { Book } from "@/types/book";

interface BookState {
  currentBook: Book | null;
  setCurrentBook: (book: Book | null) => void;
}

export const useBookStore = create<BookState>((set) => ({
  currentBook: null,
  setCurrentBook: (book) => set({ currentBook: book }),
}));
