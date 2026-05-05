import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookText,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  ListTree,
  Save,
  Settings,
  Sparkles,
  Wand2,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { listBooks } from "@/api/books";
import { statusLabel, typeLabel } from "@/pages/bookView";

const toolItems = [
  { icon: ListTree, label: "结构" },
  { icon: Wand2, label: "改写" },
  { icon: Sparkles, label: "润色" },
  { icon: FileText, label: "模板" },
  { icon: Settings, label: "设置" },
];

export default function BookEditorPage() {
  const { bookId } = useParams();
  const [catalogCollapsed, setCatalogCollapsed] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["books"],
    queryFn: listBooks,
  });

  const book = useMemo(() => data?.find((item) => item.id === bookId), [bookId, data]);

  if (isLoading) {
    return <div className="surface-panel">加载书籍信息中...</div>;
  }

  if (!book) {
    return (
      <div className="surface-panel">
        <p className="text-sm text-slate-600">未找到该书稿，可能已被删除或尚未同步。</p>
        <Link to="/app/books" className="mt-3 inline-flex text-sm text-brand hover:underline">
          返回图书管理
        </Link>
      </div>
    );
  }

  return (
    <section className="editor-shell">
      <aside className="editor-toolbar">
        {toolItems.map((tool) => {
          const Icon = tool.icon;
          return (
            <button key={tool.label} type="button" className="icon-button" title={tool.label}>
              <Icon className="h-4 w-4" />
            </button>
          );
        })}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="editor-topbar">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-medium text-ink">{book.title}</h1>
            <p className="mt-1 text-xs text-slate-500">
              {typeLabel[book.book_type]} · {statusLabel[book.status]}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" className="icon-button" title="导出">
              <Download className="h-4 w-4" />
            </button>
            <button type="button" className="icon-button" title="保存">
              <Save className="h-4 w-4" />
            </button>
          </div>
        </header>

        <div className="editor-workspace">
          <aside className={`editor-catalog ${catalogCollapsed ? "editor-catalog-collapsed" : ""}`}>
            <button
              type="button"
              className="mb-3 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
              onClick={() => setCatalogCollapsed((value) => !value)}
            >
              {catalogCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
              {catalogCollapsed ? "展开目录" : "收起目录"}
            </button>
            {!catalogCollapsed && (
              <div className="space-y-2 text-sm">
                <p className="rounded bg-brand-50 px-2 py-1 text-brand-700">章节 1：引言</p>
                <p className="rounded px-2 py-1 text-slate-600 hover:bg-slate-100">章节 2：核心方法</p>
                <p className="rounded px-2 py-1 text-slate-600 hover:bg-slate-100">章节 3：实践案例</p>
              </div>
            )}
          </aside>

          <article className="editor-canvas">
            <div className="mb-4 flex items-center gap-2 text-sm text-slate-500">
              <BookText className="h-4 w-4" />
              正文编辑区
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm leading-7 text-slate-700 shadow-sm min-h-[380px]">
              在这里开始编辑当前章节内容。后续可继续接入段落级 AI 辅助与自动保存提示。
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
