import { useQuery } from "@tanstack/react-query";
import { BookOpen, Loader2 } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";

import { addLibraryToBook, listGlobalLibrary } from "@/api/library";

type Tab = "curated" | "community" | "mine";

export default function LibraryPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("curated");
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState<string | null>(null);

  const source = tab === "curated" ? "curated" : tab === "community" ? "community" : undefined;

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["library", tab, q],
    queryFn: () =>
      listGlobalLibrary({
        source,
        q: q.trim() || undefined,
        mine: tab === "mine",
      }),
  });

  async function onAdd(itemId: string) {
    const bookId = window.prompt("请输入要加入的书稿 ID（可先打开书稿，从地址栏复制 UUID）");
    if (!bookId?.trim()) return;
    setAdding(itemId);
    try {
      await addLibraryToBook(bookId.trim(), itemId);
      toast.success("已加入引用库");
      void refetch();
    } catch {
      toast.error("加入失败");
    } finally {
      setAdding(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6 flex items-center gap-3">
        <BookOpen className="h-7 w-7 text-indigo-600" />
        <div>
          <h1 className="text-xl font-semibold text-ink">系统书库</h1>
          <p className="text-sm text-slate-500">经典 AI 文献与社区贡献，可加入书稿引用库</p>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {(
          [
            ["curated", "经典文献"],
            ["community", "社区贡献"],
            ["mine", "我的上传"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`rounded-full px-3 py-1 text-xs ${tab === id ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600"}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
        <input
          className="input ml-auto max-w-xs text-sm"
          placeholder="搜索标题…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : (
        <ul className="space-y-3">
          {(data?.items ?? []).map((item) => (
            <li key={item.id} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-medium text-ink">{item.title}</h3>
                  <p className="mt-1 text-xs text-slate-500">
                    {(item.authors ?? []).slice(0, 3).join("；")}
                    {item.year ? ` · ${item.year}` : ""}
                    {item.journal ? ` · ${item.journal}` : ""}
                  </p>
                  {item.abstract ? (
                    <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-600">{item.abstract}</p>
                  ) : null}
                  {item.tags?.length ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {item.tags.map((t) => (
                        <span key={t} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                          {t}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="btn-secondary shrink-0 text-xs"
                  disabled={adding === item.id}
                  onClick={() => void onAdd(item.id)}
                >
                  {adding === item.id ? "加入中…" : "加入书稿"}
                </button>
              </div>
            </li>
          ))}
          {!data?.items?.length ? <p className="py-12 text-center text-sm text-slate-400">暂无文献</p> : null}
        </ul>
      )}

      <p className="mt-8 text-center text-xs text-slate-400">
        上传资料时可勾选「同意公用」以贡献到社区书库 ·{" "}
        <button type="button" className="text-indigo-600 underline" onClick={() => navigate("/app/home")}>
          返回主页
        </button>
      </p>
    </div>
  );
}
