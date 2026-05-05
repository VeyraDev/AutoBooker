import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { LayoutGrid, List, Plus } from "lucide-react";

import { listBooks } from "@/api/books";
import { BookCard, BookCardSkeleton } from "@/components/books/BookCard";
import NewBookDialog from "@/components/common/NewBookDialog";
import { statusLabel, typeLabel } from "@/pages/bookView";
import type { Book } from "@/types/book";

type SortOption = "updated_desc" | "created_desc" | "title_asc";
type ViewMode = "grid" | "list";

function sortBooks(books: Book[], sortBy: SortOption) {
  const copy = [...books];
  if (sortBy === "title_asc") {
    return copy.sort((a, b) => a.title.localeCompare(b.title, "zh-CN"));
  }

  if (sortBy === "created_desc") {
    return copy.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }

  return copy.sort((a, b) => {
    const bTime = new Date(b.updated_at ?? b.created_at).getTime();
    const aTime = new Date(a.updated_at ?? a.created_at).getTime();
    return bTime - aTime;
  });
}

export default function BooksPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<"all" | Book["status"]>("all");
  const [typeFilter, setTypeFilter] = useState<"all" | Book["book_type"]>("all");
  const [sortBy, setSortBy] = useState<SortOption>("updated_desc");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["books"],
    queryFn: listBooks,
  });
  const totalBooks = data?.length ?? 0;
  const activeBooks = data?.filter((book) => book.status !== "completed").length ?? 0;
  const completedBooks = data?.filter((book) => book.status === "completed").length ?? 0;
  const filteredBooks = useMemo(() => {
    if (!data) {
      return [];
    }

    const books = data.filter((book) => {
      if (statusFilter !== "all" && book.status !== statusFilter) {
        return false;
      }
      if (typeFilter !== "all" && book.book_type !== typeFilter) {
        return false;
      }
      return true;
    });

    return sortBooks(books, sortBy);
  }, [data, sortBy, statusFilter, typeFilter]);

  return (
    <section>
      <div className="dashboard-section-title">
        <div>
          <p className="eyebrow">Library</p>
          <h1 className="page-title mt-2">图书管理</h1>
          <p className="page-subtitle">管理书稿全生命周期并直接进入编辑工作台。</p>
        </div>
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="btn-primary"
          aria-label="新建书稿"
          title="新建书稿"
        >
          <Plus className="mr-1 h-4 w-4" />
          新建书稿
        </button>
      </div>

      <div className="mb-7 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="metric-card">
          <p className="text-xs text-slate-500">书稿总数</p>
          <p className="mt-1 text-2xl font-medium text-ink">{totalBooks}</p>
        </div>
        <div className="metric-card">
          <p className="text-xs text-slate-500">进行中</p>
          <p className="mt-1 text-2xl font-medium text-brand-700">{activeBooks}</p>
        </div>
        <div className="metric-card">
          <p className="text-xs text-slate-500">已完成</p>
          <p className="mt-1 text-2xl font-medium text-emerald-600">{completedBooks}</p>
        </div>
      </div>

      <div className="book-toolbar">
        <div className="book-toolbar-group">
          <select
            className="book-select"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as "all" | Book["status"])}
          >
            <option value="all">全部状态</option>
            {Object.entries(statusLabel).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            className="book-select"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value as "all" | Book["book_type"])}
          >
            <option value="all">全部类型</option>
            {Object.entries(typeLabel).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select className="book-select" value={sortBy} onChange={(event) => setSortBy(event.target.value as SortOption)}>
            <option value="updated_desc">最近更新</option>
            <option value="created_desc">最近创建</option>
            <option value="title_asc">标题 A-Z</option>
          </select>
        </div>

        <div className="view-toggle" role="tablist" aria-label="视图模式切换">
          <button
            type="button"
            onClick={() => setViewMode("grid")}
            className={`view-toggle-button ${viewMode === "grid" ? "view-toggle-button-active" : ""}`}
          >
            <LayoutGrid className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setViewMode("list")}
            className={`view-toggle-button ${viewMode === "list" ? "view-toggle-button-active" : ""}`}
          >
            <List className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {isLoading && (
        <div className={viewMode === "grid" ? "book-grid" : "book-list"}>
          <BookCardSkeleton view={viewMode} />
          <BookCardSkeleton view={viewMode} />
          <BookCardSkeleton view={viewMode} />
        </div>
      )}

      {isError && (
        <div className="state-panel">
          <p className="mb-3 text-slate-500">加载失败，请检查后端是否启动或网络连接</p>
          <button type="button" onClick={() => refetch()} className="btn-secondary">
            重试
          </button>
        </div>
      )}

      {!isLoading && !isError && data && filteredBooks.length === 0 && (
        <div className="state-panel">
          <p className="mb-1 text-slate-500">当前筛选下没有书稿</p>
          <p className="mb-5 text-sm text-slate-400">请调整筛选条件，或点击右上角创建一本新书</p>
          <button type="button" onClick={() => setDialogOpen(true)} className="btn-primary">
            新建书稿
          </button>
        </div>
      )}

      {!isLoading && !isError && filteredBooks.length > 0 && (
        <div className={viewMode === "grid" ? "book-grid" : "book-list"}>
          {filteredBooks.map((book) => (
            <BookCard key={book.id} book={book} view={viewMode} />
          ))}
        </div>
      )}
      <NewBookDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </section>
  );
}
