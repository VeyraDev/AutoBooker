import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, FileText, Library, Plus, Search, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";

import { listBooks } from "@/api/books";
import {
  addLibraryToBook,
  addShelfItemToBook,
  listGlobalLibrary,
  listShelfCategories,
  listShelfItems,
  uploadShelfItem,
  type GlobalLiteratureItem,
  type LibraryCategory,
  type LibraryShelfItem,
} from "@/api/library";

type Tab = "shelf" | "classics";

/** 接口失败时仍展示完整分类，避免上传框只剩「其他」 */
const FALLBACK_CATEGORIES: LibraryCategory[] = [
  { id: "humanities", slug: "humanities", name: "人文社科", sort_order: 10 },
  { id: "philosophy", slug: "philosophy", name: "哲学思想", sort_order: 15 },
  { id: "history", slug: "history", name: "历史地理", sort_order: 18 },
  { id: "politics", slug: "politics", name: "政治法律", sort_order: 22 },
  { id: "education", slug: "education", name: "教育心理", sort_order: 25 },
  { id: "science", slug: "science", name: "自然科学", sort_order: 30 },
  { id: "math", slug: "math", name: "数学统计", sort_order: 32 },
  { id: "medicine", slug: "medicine", name: "医学健康", sort_order: 35 },
  { id: "tech", slug: "tech", name: "计算机与技术", sort_order: 40 },
  { id: "ai", slug: "ai", name: "人工智能", sort_order: 42 },
  { id: "engineering", slug: "engineering", name: "工程技术", sort_order: 45 },
  { id: "business", slug: "business", name: "经济管理", sort_order: 50 },
  { id: "finance", slug: "finance", name: "金融投资", sort_order: 52 },
  { id: "marketing", slug: "marketing", name: "市场运营", sort_order: 55 },
  { id: "textbook", slug: "textbook", name: "教材讲义", sort_order: 60 },
  { id: "exam", slug: "exam", name: "考试考证", sort_order: 62 },
  { id: "literature", slug: "literature", name: "文学艺术", sort_order: 70 },
  { id: "language", slug: "language", name: "语言写作", sort_order: 72 },
  { id: "design", slug: "design", name: "设计创意", sort_order: 75 },
  { id: "reference", slug: "reference", name: "工具参考", sort_order: 80 },
  { id: "report", slug: "report", name: "报告白皮书", sort_order: 85 },
  { id: "biography", slug: "biography", name: "人物传记", sort_order: 88 },
  { id: "other", slug: "other", name: "其他", sort_order: 99 },
];

function formatSize(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function LibraryPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("shelf");
  const [q, setQ] = useState("");
  const [category, setCategory] = useState<string>("");
  const [mine, setMine] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [pickItem, setPickItem] = useState<LibraryShelfItem | null>(null);
  const [pickClassic, setPickClassic] = useState<GlobalLiteratureItem | null>(null);

  const catsQuery = useQuery({
    queryKey: ["library-categories"],
    queryFn: listShelfCategories,
  });

  const shelfQuery = useQuery({
    queryKey: ["library-shelf", category, q, mine],
    queryFn: () => listShelfItems({ category: category || undefined, q: q || undefined, mine }),
    enabled: tab === "shelf",
  });

  const classicsQuery = useQuery({
    queryKey: ["library-classics", q],
    queryFn: () => listGlobalLibrary({ q: q || undefined }),
    enabled: tab === "classics",
  });

  const booksQuery = useQuery({
    queryKey: ["books"],
    queryFn: listBooks,
    enabled: Boolean(pickItem || pickClassic),
  });

  const categories =
    (catsQuery.data && catsQuery.data.length > 0
      ? catsQuery.data
      : shelfQuery.data?.categories && shelfQuery.data.categories.length > 0
        ? shelfQuery.data.categories
        : FALLBACK_CATEGORIES) ?? FALLBACK_CATEGORIES;
  const shelfItems = shelfQuery.data?.items ?? [];
  const classics = classicsQuery.data?.items ?? [];

  const uploadMut = useMutation({
    mutationFn: uploadShelfItem,
    onSuccess: () => {
      toast.success("已上传到共享书架");
      setUploadOpen(false);
      void qc.invalidateQueries({ queryKey: ["library-shelf"] });
    },
    onError: (e: Error) => toast.error(e.message || "上传失败"),
  });

  const addShelfMut = useMutation({
    mutationFn: ({ bookId, itemId }: { bookId: string; itemId: string }) => addShelfItemToBook(bookId, itemId),
    onSuccess: (_data, vars) => {
      toast.success("已加入书稿参考文献（后台解析中）");
      setPickItem(null);
      void qc.invalidateQueries({ queryKey: ["library-shelf"] });
      navigate(`/app/books/${vars.bookId}`);
    },
    onError: (e: Error) => toast.error(e.message || "加入失败"),
  });

  const addClassicMut = useMutation({
    mutationFn: ({ bookId, literatureId }: { bookId: string; literatureId: string }) =>
      addLibraryToBook(bookId, literatureId),
    onSuccess: (_data, vars) => {
      toast.success("已加入本书引用");
      setPickClassic(null);
      navigate(`/app/books/${vars.bookId}`);
    },
    onError: (e: Error) => toast.error(e.message || "加入失败"),
  });

  const books = useMemo(() => booksQuery.data ?? [], [booksQuery.data]);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Library className="h-7 w-7 text-indigo-600" />
          <div>
            <h1 className="text-xl font-semibold text-ink">共享书架</h1>
            <p className="text-sm text-slate-500">上传电子书供大家参考，也可把资料加入你的书稿</p>
          </div>
        </div>
        {tab === "shelf" ? (
          <button type="button" className="btn-primary inline-flex items-center gap-1.5 text-sm" onClick={() => setUploadOpen(true)}>
            <Upload className="h-4 w-4" />
            上传电子书
          </button>
        ) : null}
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-2 border-b border-slate-200 pb-3">
        <button
          type="button"
          className={`rounded-lg px-3 py-1.5 text-sm ${tab === "shelf" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"}`}
          onClick={() => setTab("shelf")}
        >
          共享书架
        </button>
        <button
          type="button"
          className={`rounded-lg px-3 py-1.5 text-sm ${tab === "classics" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"}`}
          onClick={() => setTab("classics")}
        >
          经典文献
        </button>
        <div className="ml-auto flex min-w-[220px] flex-1 items-center gap-2 sm:max-w-xs">
          <div className="relative w-full">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-8 pr-3 text-sm outline-none focus:border-slate-400"
              placeholder="搜索标题…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
        </div>
      </div>

      {tab === "shelf" ? (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className={`rounded-full px-3 py-1 text-xs ${!category ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700"}`}
              onClick={() => setCategory("")}
            >
              全部
            </button>
            {categories.map((c) => (
              <button
                key={c.id}
                type="button"
                className={`rounded-full px-3 py-1 text-xs ${category === c.slug ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700"}`}
                onClick={() => setCategory(c.slug)}
                title={c.description || c.name}
              >
                {c.name}
              </button>
            ))}
            <label className="ml-auto flex items-center gap-1.5 text-xs text-slate-600">
              <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
              只看我上传的
            </label>
          </div>

          {shelfQuery.isLoading ? (
            <p className="py-16 text-center text-sm text-slate-400">加载中…</p>
          ) : shelfQuery.isError ? (
            <p className="py-16 text-center text-sm text-rose-600">加载失败，请确认后端已启动并完成迁移</p>
          ) : shelfItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/80 px-6 py-16 text-center">
              <BookOpen className="mb-3 h-9 w-9 text-slate-400" />
              <p className="font-medium text-ink">书架还是空的</p>
              <p className="mt-1 max-w-md text-sm text-slate-500">上传 PDF / Word / TXT，大家都可以浏览并加入自己的书稿作参考。</p>
              <button type="button" className="btn-primary mt-6 text-sm" onClick={() => setUploadOpen(true)}>
                <Plus className="mr-1 inline h-4 w-4" />
                上传第一本
              </button>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {shelfItems.map((item) => (
                <article key={item.id} className="flex flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="mb-2 flex items-start justify-between gap-2">
                    <h2 className="line-clamp-2 text-sm font-semibold text-ink">{item.title}</h2>
                    <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase text-slate-600">
                      {item.file_type}
                    </span>
                  </div>
                  <p className="mb-2 line-clamp-2 text-xs text-slate-500">
                    {(item.authors || []).join("、") || "作者未填"}
                    {item.category_name ? ` · ${item.category_name}` : ""}
                  </p>
                  {item.description ? <p className="mb-3 line-clamp-3 text-xs leading-relaxed text-slate-600">{item.description}</p> : null}
                  <div className="mt-auto flex items-center justify-between gap-2 pt-2 text-[11px] text-slate-400">
                    <span>
                      {formatSize(item.size_bytes)} · 使用 {item.use_count} 次
                      {item.uploader_name ? ` · ${item.uploader_name}` : ""}
                    </span>
                    <button type="button" className="btn-secondary px-2 py-1 text-[11px]" onClick={() => setPickItem(item)}>
                      加入书稿
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          {classicsQuery.isLoading ? (
            <p className="py-16 text-center text-sm text-slate-400">加载中…</p>
          ) : classics.length === 0 ? (
            <p className="py-16 text-center text-sm text-slate-400">暂无经典文献</p>
          ) : (
            <ul className="space-y-2">
              {classics.map((item) => (
                <li key={item.id} className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">{item.title}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {(item.authors || []).join(", ") || "—"}
                      {item.year ? ` · ${item.year}` : ""}
                      {item.journal ? ` · ${item.journal}` : ""}
                    </p>
                    {item.abstract ? <p className="mt-1 line-clamp-2 text-xs text-slate-600">{item.abstract}</p> : null}
                  </div>
                  <button type="button" className="btn-secondary shrink-0 px-2 py-1 text-[11px]" onClick={() => setPickClassic(item)}>
                    加入引用
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <p className="mt-8 text-center text-[11px] text-slate-400">
        上传内容仅供学习参考；请确保你有权分享该资料。
        <Link to="/app/books" className="ml-2 text-indigo-600 hover:underline">
          返回我的书稿
        </Link>
      </p>

      {uploadOpen ? (
        <UploadDialog
          categories={categories}
          busy={uploadMut.isPending}
          onClose={() => setUploadOpen(false)}
          onSubmit={(payload) => uploadMut.mutate(payload)}
        />
      ) : null}

      {(pickItem || pickClassic) && (
        <PickBookDialog
          title={pickItem ? `将「${pickItem.title}」加入哪本书稿？` : `将「${pickClassic?.title}」加入哪本书稿？`}
          books={books}
          loading={booksQuery.isLoading}
          busy={addShelfMut.isPending || addClassicMut.isPending}
          onClose={() => {
            setPickItem(null);
            setPickClassic(null);
          }}
          onPick={(bookId) => {
            if (pickItem) addShelfMut.mutate({ bookId, itemId: pickItem.id });
            else if (pickClassic) addClassicMut.mutate({ bookId, literatureId: pickClassic.id });
          }}
        />
      )}
    </div>
  );
}

function UploadDialog({
  categories,
  busy,
  onClose,
  onSubmit,
}: {
  categories: Array<{ slug: string; name: string }>;
  busy: boolean;
  onClose: () => void;
  onSubmit: (p: {
    file: File;
    title: string;
    authors: string[];
    description: string;
    category_slug: string;
    tags: string[];
  }) => void;
}) {
  const categoryOptions = categories.length > 0 ? categories : FALLBACK_CATEGORIES;
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [authors, setAuthors] = useState("");
  const [description, setDescription] = useState("");
  const [categorySlug, setCategorySlug] = useState(
    () => categoryOptions.find((c) => c.slug !== "other")?.slug || categoryOptions[0]?.slug || "humanities",
  );
  const [tags, setTags] = useState("");

  return (
    <div className="fixed inset-0 z-[300] flex items-center justify-center bg-slate-900/50 px-4">
      <div className="absolute inset-0" onClick={() => !busy && onClose()} aria-hidden />
      <div className="relative z-[301] w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl">
        <h3 className="text-base font-semibold text-ink">上传到共享书架</h3>
        <p className="mt-1 text-xs text-slate-500">支持 PDF / DOCX / TXT，上传后全站可见</p>
        <div className="mt-4 space-y-3">
          <label className="block text-xs text-slate-600">
            <span className="mb-1 block font-medium">文件</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,application/pdf"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0] || null;
                setFile(f);
                if (f && !title) setTitle(f.name.replace(/\.[^.]+$/, ""));
              }}
            />
          </label>
          <label className="block text-xs text-slate-600">
            <span className="mb-1 block font-medium">书名 / 资料名</span>
            <input
              className="w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm"
              value={title}
              disabled={busy}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="block text-xs text-slate-600">
            <span className="mb-1 block font-medium">作者（逗号分隔）</span>
            <input
              className="w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm"
              value={authors}
              disabled={busy}
              onChange={(e) => setAuthors(e.target.value)}
            />
          </label>
          <label className="block text-xs text-slate-600">
            <span className="mb-1 block font-medium">分类</span>
            <select
              className="w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm"
              value={categorySlug}
              disabled={busy}
              onChange={(e) => setCategorySlug(e.target.value)}
            >
              {categoryOptions.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-slate-600">
            <span className="mb-1 block font-medium">简介</span>
            <textarea
              className="w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm"
              rows={3}
              value={description}
              disabled={busy}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <label className="block text-xs text-slate-600">
            <span className="mb-1 block font-medium">标签（逗号分隔）</span>
            <input
              className="w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm"
              value={tags}
              disabled={busy}
              onChange={(e) => setTags(e.target.value)}
            />
          </label>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-secondary text-sm" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary text-sm"
            disabled={busy || !file}
            onClick={() => {
              if (!file) return;
              onSubmit({
                file,
                title: title.trim() || file.name,
                authors: authors
                  .split(/[,，、]/)
                  .map((s) => s.trim())
                  .filter(Boolean),
                description: description.trim(),
                category_slug: categorySlug || "other",
                tags: tags
                  .split(/[,，、]/)
                  .map((s) => s.trim())
                  .filter(Boolean),
              });
            }}
          >
            {busy ? "上传中…" : "上传并上架"}
          </button>
        </div>
      </div>
    </div>
  );
}

function PickBookDialog({
  title,
  books,
  loading,
  busy,
  onClose,
  onPick,
}: {
  title: string;
  books: Array<{ id: string; title: string }>;
  loading: boolean;
  busy: boolean;
  onClose: () => void;
  onPick: (bookId: string) => void;
}) {
  return (
    <div className="fixed inset-0 z-[300] flex items-center justify-center bg-slate-900/50 px-4">
      <div className="absolute inset-0" onClick={() => !busy && onClose()} aria-hidden />
      <div className="relative z-[301] w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl">
        <h3 className="text-base font-semibold text-ink">{title}</h3>
        <div className="mt-4 max-h-72 space-y-1 overflow-y-auto">
          {loading ? <p className="py-6 text-center text-xs text-slate-400">加载书稿…</p> : null}
          {!loading && books.length === 0 ? (
            <p className="py-6 text-center text-xs text-slate-500">
              还没有书稿。
              <Link to="/app/books" className="ml-1 text-indigo-600" onClick={onClose}>
                去创建
              </Link>
            </p>
          ) : null}
          {books.map((b) => (
            <button
              key={b.id}
              type="button"
              disabled={busy}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
              onClick={() => onPick(b.id)}
            >
              <FileText className="h-4 w-4 shrink-0 text-slate-400" />
              <span className="truncate">{b.title}</span>
            </button>
          ))}
        </div>
        <div className="mt-4 flex justify-end">
          <button type="button" className="btn-secondary text-sm" disabled={busy} onClick={onClose}>
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
