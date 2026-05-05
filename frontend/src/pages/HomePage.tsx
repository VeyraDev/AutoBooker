import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";

import { listBooks } from "@/api/books";
import { statusLabel } from "@/pages/bookView";

export default function HomePage() {
  const { data } = useQuery({
    queryKey: ["books"],
    queryFn: listBooks,
  });

  const books = data ?? [];
  const activeBooks = books.filter((book) => book.status !== "completed");
  const recentBooks = [...books]
    .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
    .slice(0, 5);

  return (
    <section className="space-y-8">
      <div className="surface-panel">
        <p className="eyebrow">Workspace</p>
        <h1 className="page-title mt-2">创作主页</h1>
        <p className="page-subtitle">查看整体进度并延续你当前的写作节奏。</p>
        <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-3">
          <div className="metric-card">
            <p className="metric-title">总书稿</p>
            <p className="metric-value">{books.length}</p>
          </div>
          <div className="metric-card">
            <p className="metric-title">进行中</p>
            <p className="metric-value text-brand-700">{activeBooks.length}</p>
          </div>
          <div className="metric-card">
            <p className="metric-title">已完成</p>
            <p className="metric-value text-emerald-600">{books.length - activeBooks.length}</p>
          </div>
        </div>
      </div>

      <div className="surface-panel">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-medium tracking-tight text-ink">最近更新</h2>
          <Link
            to="/app/books"
            className="inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"
            aria-label="查看全部书稿"
            title="查看全部书稿"
          >
            查看全部
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="mt-5 space-y-3">
          {recentBooks.length === 0 ? (
            <p className="text-sm text-slate-500">暂无书稿，去图书管理创建第一本书。</p>
          ) : (
            recentBooks.map((book) => (
              <Link
                key={book.id}
                to={`/app/books/${book.id}`}
                className="list-row-link"
                aria-label={`打开书稿 ${book.title}`}
                title={book.title}
              >
                <span className="truncate text-sm text-slate-700">{book.title}</span>
                <span className="ml-3 shrink-0 text-xs text-slate-500">{statusLabel[book.status]}</span>
              </Link>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
