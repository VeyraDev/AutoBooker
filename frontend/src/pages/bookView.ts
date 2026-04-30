import type { BookStatus, BookType } from "@/types/book";

export const statusLabel: Record<BookStatus, string> = {
  setup: "设定中",
  outline_generating: "大纲生成中",
  outline_ready: "大纲就绪",
  writing: "写作中",
  review_ready: "待审校",
  completed: "已完成",
};

export const statusTone: Record<BookStatus, string> = {
  setup: "bg-slate-100 text-slate-600",
  outline_generating: "bg-amber-50 text-amber-700",
  outline_ready: "bg-amber-50 text-amber-700",
  writing: "bg-brand-50 text-brand-700",
  review_ready: "bg-violet-50 text-violet-700",
  completed: "bg-emerald-50 text-emerald-700",
};

export const typeLabel: Record<BookType, string> = {
  nonfiction: "大众非虚构",
  academic: "学术专著",
};
