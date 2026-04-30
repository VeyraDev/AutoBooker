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

const coverGradients = [
  "from-[#5B56A8] via-[#6D68BC] to-[#8C88D4]",
  "from-[#425F93] via-[#5475A6] to-[#7392BE]",
  "from-[#3C6E72] via-[#4C8587] to-[#6DA4A6]",
  "from-[#755A7F] via-[#8A6A95] to-[#A686B0]",
];

function pickGradient(bookId: string) {
  const code = [...bookId].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return coverGradients[code % coverGradients.length];
}

function buildUpdatedLabel(book: Book) {
  const timestamp = book.updated_at ?? book.created_at;
  const parsed = new Date(timestamp);
  return `更新于 ${parsed.toLocaleDateString()}`;
}

function BookCover({ book }: { book: Book }) {
  const cover = book.cover_url?.trim();
  if (cover) {
    return <img src={cover} alt={`${book.title} 封面`} className="book-cover-image" loading="lazy" />;
  }

  return (
    <div className={`book-cover-fallback bg-gradient-to-br ${pickGradient(book.id)}`}>
      <span className="book-cover-monogram">{book.title.slice(0, 1).toUpperCase()}</span>
      <span className="book-cover-kind">{typeLabel[book.book_type]}</span>
    </div>
  );
}

export function BookCard({ book, view = "grid" }: { book: Book; view?: "grid" | "list" }) {
  return (
    <Link to={`/app/books/${book.id}`} className="block" aria-label={`打开书稿 ${book.title}`} title={book.title}>
      <article className={`book-card ${view === "list" ? "book-card-list" : ""}`}>
        <div className="book-card-cover-wrap">
          <BookCover book={book} />
          <span className={`book-status-badge ${statusTone[book.status]}`}>{statusLabel[book.status]}</span>
        </div>

        <div className="book-card-body">
          <h3 className="book-card-title">{book.title}</h3>
          <div className="book-card-meta">
            <span>{typeLabel[book.book_type]}</span>
            {book.target_words ? <span>目标 {book.target_words.toLocaleString()} 字</span> : <span>未设置目标字数</span>}
          </div>
          <div className="book-card-progress-track" aria-hidden="true">
            <div className="book-card-progress-fill" style={{ width: `${statusProgress[book.status]}%` }} />
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

export function BookCardSkeleton({ view = "grid" }: { view?: "grid" | "list" }) {
  return (
    <article className={`book-card animate-pulse ${view === "list" ? "book-card-list" : ""}`}>
      <div className="book-card-cover-wrap">
        <div className="h-full w-full rounded-[inherit] bg-slate-200" />
      </div>
      <div className="book-card-body">
        <div className="mb-3 h-4 w-3/4 rounded bg-slate-200" />
        <div className="mb-2 h-3 w-full rounded bg-slate-200" />
        <div className="mb-3 h-3 w-2/3 rounded bg-slate-200" />
        <div className="mb-3 h-1.5 w-full rounded-full bg-slate-200" />
        <div className="h-3 w-1/2 rounded bg-slate-200" />
      </div>
    </article>
  );
}
