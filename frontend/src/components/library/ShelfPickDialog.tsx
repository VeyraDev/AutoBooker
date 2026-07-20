import { useQuery } from "@tanstack/react-query";
import { Library, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import { listShelfItems, type LibraryShelfItem } from "@/api/library";

type Props = {
  open: boolean;
  busy?: boolean;
  title?: string;
  onClose: () => void;
  onPick: (item: LibraryShelfItem) => void | Promise<void>;
};

function formatSize(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ShelfPickDialog({
  open,
  busy,
  title = "从共享书架选择",
  onClose,
  onPick,
}: Props) {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [pickingId, setPickingId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["library-shelf-pick", category, q],
    queryFn: () => listShelfItems({ category: category || undefined, q: q || undefined, limit: 60 }),
    enabled: open,
  });

  const categories = query.data?.categories ?? [];
  const items = query.data?.items ?? [];
  const filteredHint = useMemo(() => {
    if (query.isLoading) return "加载书架…";
    if (query.isError) return "加载失败，请稍后重试";
    if (!items.length) return "书架暂无资料，请先到「共享书架」上传";
    return null;
  }, [query.isLoading, query.isError, items.length]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[420] flex items-center justify-center bg-slate-900/50 px-4">
      <div className="absolute inset-0" aria-hidden onClick={() => !busy && !pickingId && onClose()} />
      <div className="relative z-[421] flex max-h-[min(88vh,720px)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-2">
            <Library className="h-5 w-5 text-indigo-600" />
            <div>
              <h3 className="text-sm font-semibold text-ink">{title}</h3>
              <p className="text-[11px] text-slate-500">选择后将加入当前书稿并解析</p>
            </div>
          </div>
          <button
            type="button"
            className="icon-button h-8 w-8"
            disabled={Boolean(busy || pickingId)}
            onClick={onClose}
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-2 border-b border-slate-100 px-4 py-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              className="w-full rounded-lg border border-slate-200 py-2 pl-8 pr-3 text-sm outline-none focus:border-slate-400"
              placeholder="搜索书名…"
              value={q}
              disabled={Boolean(busy || pickingId)}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              className={`rounded-full px-2.5 py-1 text-[11px] ${!category ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700"}`}
              disabled={Boolean(busy || pickingId)}
              onClick={() => setCategory("")}
            >
              全部
            </button>
            {categories.map((c) => (
              <button
                key={c.id}
                type="button"
                className={`rounded-full px-2.5 py-1 text-[11px] ${category === c.slug ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700"}`}
                disabled={Boolean(busy || pickingId)}
                onClick={() => setCategory(c.slug)}
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          {filteredHint ? <p className="py-10 text-center text-xs text-slate-400">{filteredHint}</p> : null}
          <ul className="space-y-2">
            {items.map((item) => {
              const picking = pickingId === item.id;
              return (
                <li
                  key={item.id}
                  className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">{item.title}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      {(item.authors || []).join("、") || "作者未填"}
                      {item.category_name ? ` · ${item.category_name}` : ""}
                      {` · ${item.file_type.toUpperCase()} · ${formatSize(item.size_bytes)}`}
                    </p>
                    {item.description ? (
                      <p className="mt-1 line-clamp-2 text-[11px] text-slate-600">{item.description}</p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="btn-primary shrink-0 px-2.5 py-1 text-[11px]"
                    disabled={Boolean(busy || pickingId)}
                    onClick={() => {
                      setPickingId(item.id);
                      void Promise.resolve(onPick(item)).finally(() => setPickingId(null));
                    }}
                  >
                    {picking ? "添加中…" : "选择"}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}
