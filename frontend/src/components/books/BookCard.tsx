import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MoreHorizontal, Star } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";

import { deleteBook, updateBook } from "@/api/books";
import { statusLabel, statusTone, typeLabel } from "@/pages/bookView";
import type { Book } from "@/types/book";

const PIN_KEY = "autobooker_books_pin_order";

function pinBookToFront(bookId: string) {
  try {
    const raw = window.localStorage.getItem(PIN_KEY);
    let arr: string[] = [];
    if (raw) {
      const j = JSON.parse(raw) as unknown;
      arr = Array.isArray(j) ? j.filter((x) => typeof x === "string") : [];
    }
    const next = [bookId, ...arr.filter((id) => id !== bookId)];
    window.localStorage.setItem(PIN_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
}

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
  onPinned,
}: {
  book: Book;
  view?: "grid" | "list";
  isHero?: boolean;
  onPinned?: () => void;
}) {
  const qc = useQueryClient();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function onDoc(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  const delMutation = useMutation({
    mutationFn: () => deleteBook(book.id),
    onSuccess: async () => {
      toast.success("已删除");
      await qc.invalidateQueries({ queryKey: ["books"] });
      setMenuOpen(false);
    },
    onError: () => toast.error("删除失败"),
  });

  function handleRename() {
    setMenuOpen(false);
    const next = window.prompt("重命名书稿", book.title);
    if (next == null) return;
    const t = next.trim();
    if (!t) {
      toast.error("标题不能为空");
      return;
    }
    updateBook(book.id, { title: t })
      .then(async () => {
        toast.success("已更新书名");
        await qc.invalidateQueries({ queryKey: ["books"] });
      })
      .catch(() => toast.error("更新失败"));
  }

  function handleFavorite() {
    pinBookToFront(book.id);
    onPinned?.();
    toast.success("已置顶");
    setMenuOpen(false);
  }

  function handleDelete() {
    setMenuOpen(false);
    if (!window.confirm(`确定删除《${book.title || "未命名"}》？此操作不可恢复。`)) return;
    delMutation.mutate();
  }

  return (
    <div className={`book-card-wrapper relative${isHero ? " book-card-wrapper--hero" : ""}`}>
      <Link
        to={`/app/books/${book.id}`}
        className={`book-card-link block${isHero ? " book-card-link--hero" : ""}`}
        aria-label={`打开书稿 ${book.title}`}
        title={book.title}
      >
        <article className={`book-card ${view === "list" ? "book-card-list" : ""}${isHero ? " book-card--hero" : ""}`}>
          <div className="book-card-body">
            <span className="book-icon-block" aria-hidden>
              {book.title.slice(0, 1).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1 pr-8">
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

      <div ref={menuRef} className="absolute right-2 top-2 z-20">
        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200/90 bg-white/95 text-slate-600 shadow-sm backdrop-blur-sm hover:bg-slate-50 hover:text-slate-900"
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          aria-label="更多操作"
          title="更多"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setMenuOpen((v) => !v);
          }}
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
        {menuOpen ? (
          <div
            role="menu"
            className="absolute right-0 top-[calc(100%+6px)] min-w-[10rem] rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              role="menuitem"
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-ink hover:bg-slate-50"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleFavorite();
              }}
            >
              <Star className="h-3.5 w-3.5 shrink-0 text-amber-500" />
              收藏（置顶）
            </button>
            <button
              type="button"
              role="menuitem"
              className="w-full px-3 py-2 text-left text-ink hover:bg-slate-50"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleRename();
              }}
            >
              重命名
            </button>
            <button
              type="button"
              role="menuitem"
              className="w-full px-3 py-2 text-left text-red-600 hover:bg-red-50"
              disabled={delMutation.isPending}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleDelete();
              }}
            >
              删除
            </button>
          </div>
        ) : null}
      </div>
    </div>
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
