import { Link } from "react-router-dom";

import { statusLabel, statusTone, typeLabel } from "@/pages/bookView";
import type { Book } from "@/types/book";

const statusProgress: Record<Book["status"], number> = {
  setup: 12,
  outline_generating: 28,
  outline_ready: 44,
  writing: 72,
  review_ready: 88,
  completed: 100,
};

function buildUpdatedLabel(book: Book) {
  const timestamp = book.updated_at ?? book.created_at;
  const parsed = new Date(timestamp);
  return `更新于 ${parsed.toLocaleDateString()}`;
}

export function BookCard({
  book,
  view = "list",
  isHero,
}: {
  book: Book;
  view?: "grid" | "list";
  /** 最近更新列表首位：主入口高亮 */
  isHero?: boolean;
}) {
  return (
    <Link
      to={`/app/books/${book.id}`}
      className={`book-card-wrapper block${isHero ? " book-card-wrapper--hero" : ""}`}
      aria-label={`打开书稿 ${book.title}`}
      title={book.title}
    >
      <article className={`book-card ${view === "list" ? "book-card-list" : ""}${isHero ? " book-card--hero" : ""}`}>
        <div className="book-card-body">
          <span className="book-icon-block" aria-hidden>
            {book.title.slice(0, 1).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="book-card-title">{book.title}</h3>
            <div className="book-card-meta">
              <span>{typeLabel[book.book_type]}</span>
              {book.target_words ? <span>目标 {book.target_words.toLocaleString()} 字</span> : <span>未设置目标字数</span>}
              <span className={`book-status-badge ${statusTone[book.status]}`}>{statusLabel[book.status]}</span>
            </div>
            <div className="mt-3 book-card-progress-track" aria-hidden="true">
              <div className="book-card-progress-fill" style={{ width: `${statusProgress[book.status]}%` }} />
            </div>
          </div>
          <div className="book-card-foot">
            <span>{buildUpdatedLabel(book)}</span>
            <span>进度 {statusProgress[book.status]}%</span>
          </div>
        </div>
      </article>
    </Link>
  );
}

export function BookCardSkeleton({ view = "list" }: { view?: "grid" | "list" }) {
  return (
    <article className={`book-card animate-pulse ${view === "list" ? "book-card-list" : ""}`}>
      <div className="book-card-body">
        <div className="h-8 w-8 rounded-[4px] bg-slate-200" />
        <div className="min-w-0 flex-1">
          <div className="mb-3 h-4 w-2/5 rounded bg-slate-200" />
          <div className="mb-3 h-3 w-3/4 rounded bg-slate-200" />
          <div className="h-2 w-full rounded-[4px] bg-slate-200" />
        </div>
        <div className="flex min-w-[160px] flex-col items-end gap-2">
          <div className="h-3 w-24 rounded bg-slate-200" />
          <div className="h-3 w-16 rounded bg-slate-200" />
        </div>
      </div>
    </article>
  );
}
