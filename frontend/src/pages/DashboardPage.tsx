import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { listBooks } from "@/api/books";
import { BookCard, BookCardSkeleton } from "@/components/books/BookCard";
import NewBookDialog from "@/components/common/NewBookDialog";
import TopBar from "@/components/layout/TopBar";
import type { Book } from "@/types/book";

export default function DashboardPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["books"],
    queryFn: listBooks,
  });
  const totalBooks = data?.length ?? 0;
  const activeBooks = data?.filter((book) => book.status !== "completed").length ?? 0;
  const completedBooks = data?.filter((book) => book.status === "completed").length ?? 0;
  const recentBooks = useMemo(() => {
    if (!data) {
      return [];
    }
    return [...data]
      .sort((a: Book, b: Book) => {
        const bTime = new Date(b.updated_at ?? b.created_at).getTime();
        const aTime = new Date(a.updated_at ?? a.created_at).getTime();
        return bTime - aTime;
      })
      .slice(0, 6);
  }, [data]);

  return (
    <div className="min-h-full flex flex-col">
      <TopBar />
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <div className="dashboard-section-title">
          <div>
            <p className="eyebrow">Workspace</p>
            <h1 className="page-title mt-2">我的书稿</h1>
            <p className="page-subtitle">从最近更新的项目快速继续创作，保持写作节奏。</p>
          </div>
          <button
            type="button"
            onClick={() => setDialogOpen(true)}
            className="btn-primary"
          >
            <Plus className="mr-1 h-4 w-4" />
            新建书稿
          </button>
        </div>

        <section className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="metric-card">
            <p className="text-xs text-slate-500">书稿总数</p>
            <p className="mt-1 text-2xl font-semibold text-ink">{totalBooks}</p>
          </div>
          <div className="metric-card">
            <p className="text-xs text-slate-500">进行中</p>
            <p className="mt-1 text-2xl font-semibold text-brand-700">{activeBooks}</p>
          </div>
          <div className="metric-card">
            <p className="text-xs text-slate-500">已完成</p>
            <p className="mt-1 text-2xl font-semibold text-emerald-600">{completedBooks}</p>
          </div>
        </section>

        {isLoading && (
          <div className="book-grid">
            <BookCardSkeleton />
            <BookCardSkeleton />
            <BookCardSkeleton />
          </div>
        )}

        {isError && (
          <div className="card text-center py-10">
            <p className="text-slate-500 mb-3">加载失败，请检查后端是否启动或网络连接</p>
            <button type="button" onClick={() => refetch()} className="btn-secondary">
              重试
            </button>
          </div>
        )}

        {!isLoading && !isError && data && data.length === 0 && (
          <div className="state-panel">
            <p className="text-slate-500 mb-1">还没有书稿</p>
            <p className="text-slate-400 text-sm mb-5">点击右上角「新建书稿」开始你的第一本</p>
            <button type="button" onClick={() => setDialogOpen(true)} className="btn-primary">
              新建第一本
            </button>
          </div>
        )}

        {!isLoading && !isError && recentBooks.length > 0 && (
          <div className="book-grid">
            {recentBooks.map((book) => (
              <BookCard key={book.id} book={book} />
            ))}
          </div>
        )}
      </main>
      <NewBookDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </div>
  );
}
