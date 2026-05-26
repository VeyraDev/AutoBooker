import { ExternalLink, Loader2, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";

import { listCitations, syncBibliographyChapter } from "@/api/citations";
import {
  addSelectedLiterature,
  insertSelectedLiteratureQuotes,
  searchLiterature,
} from "@/api/literature";
import type { CitationStyle } from "@/types/book";
import {
  literaturePaperKey,
  literaturePaperUrl,
  type CitationRecord,
  type LiteraturePaper,
  type LiteratureQuoteBlock,
} from "@/types/literature";

type Props = {
  bookId: string;
  citationStyle: CitationStyle | null;
  defaultQuery?: string;
  /** setup：设定页仅入库；editor：写作页可插入正文 */
  mode?: "setup" | "editor";
  /** 嵌入卡片时隐藏组件内小标题 */
  embedded?: boolean;
  onInsertQuotes?: (quotes: LiteratureQuoteBlock[]) => void;
};

export default function LiteraturePanel({
  bookId,
  citationStyle,
  defaultQuery = "",
  mode = "editor",
  embedded = false,
  onInsertQuotes,
}: Props) {
  const isSetup = mode === "setup";
  const [query, setQuery] = useState(defaultQuery);
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<LiteraturePaper[]>([]);
  const [sourceHint, setSourceHint] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<CitationRecord[]>([]);
  const [savedLoading, setSavedLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const refreshSaved = useCallback(async () => {
    setSavedLoading(true);
    try {
      setSaved(await listCitations(bookId));
    } catch {
      setSaved([]);
    } finally {
      setSavedLoading(false);
    }
  }, [bookId]);

  useEffect(() => {
    void refreshSaved();
  }, [refreshSaved]);

  useEffect(() => {
    if (defaultQuery.trim()) setQuery(defaultQuery.trim());
  }, [defaultQuery]);

  async function runSearch() {
    const q = query.trim();
    if (!q) {
      toast.error("请输入检索词");
      return;
    }
    setSearching(true);
    setSelected(new Set());
    try {
      const res = await searchLiterature(bookId, q, 25);
      setResults(res.items);
      setSourceHint(res.source_hint || "");
      if (!res.items.length) toast("未找到相关文献，可尝试英文关键词或换检索词");
    } catch {
      toast.error("文献检索失败");
      setResults([]);
      setSourceHint("");
    } finally {
      setSearching(false);
    }
  }

  function toggle(p: LiteraturePaper) {
    const k = literaturePaperKey(p);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  }

  const selectedPapers = results.filter((p) => selected.has(literaturePaperKey(p)));

  async function handleAddToLibrary(syncBibliography = false) {
    if (!selectedPapers.length) {
      toast.error("请先勾选文献");
      return;
    }
    if (!citationStyle) {
      toast.error("请先在「写作参数」中选择引用格式并保存设定");
      return;
    }
    setBusy(true);
    try {
      await addSelectedLiterature(bookId, selectedPapers);
      if (syncBibliography) {
        await syncBibliographyChapter(bookId);
      }
      await refreshSaved();
      setSelected(new Set());
      toast.success(
        syncBibliography
          ? `已加入 ${selectedPapers.length} 条并同步书末参考文献章节`
          : `已加入引用库（${selectedPapers.length} 条）`,
      );
    } catch {
      toast.error("加入引用库失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleInsertSelected() {
    if (!selectedPapers.length) {
      toast.error("请先勾选文献");
      return;
    }
    if (!citationStyle) {
      toast.error("请先在书稿设定中选择引用格式");
      return;
    }
    setBusy(true);
    try {
      const { quotes } = await insertSelectedLiteratureQuotes(bookId, selectedPapers);
      const usable = quotes.filter((q) => q.quote_body?.trim());
      if (!usable.length) {
        toast.error("未能抓取可引用正文，请换一条文献或稍后重试");
        return;
      }
      onInsertQuotes?.(usable);
      const partial = usable.some((q) => q.fetch_status !== "ok");
      toast.success(
        partial
          ? `已插入 ${usable.length} 段引用（部分为摘要摘录）`
          : `已插入 ${usable.length} 段可引用正文，并同步参考文献章节`,
      );
      await refreshSaved();
      setSelected(new Set());
    } catch {
      toast.error("插入引用失败");
    } finally {
      setBusy(false);
    }
  }

  const hintText = sourceHint
    ? `当前书类检索源：${sourceHint}。勾选后插入正文将抓取并解析可引用片段（非仅标记）。`
    : isSetup
      ? "按书类自动选择检索源；勾选后加入本书引用库。"
      : "检索结果按被引量与年份综合排序；标题可点击跳转原文。";

  return (
    <div className="space-y-4 text-sm">
      <div className="space-y-2">
        {!embedded ? (
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">文献检索</p>
        ) : null}
        <p className="text-[11px] leading-relaxed text-slate-500">{hintText}</p>
        <div className="flex gap-2">
          <input
            className="input h-9 flex-1 text-sm"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="标题、作者、关键词…"
            onKeyDown={(e) => {
              if (e.key === "Enter") void runSearch();
            }}
          />
          <button
            type="button"
            className="btn-secondary flex h-9 shrink-0 items-center gap-1 px-3 text-xs"
            disabled={searching}
            onClick={() => void runSearch()}
          >
            {searching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            搜索
          </button>
        </div>
      </div>

      {results.length > 0 ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-slate-500">检索结果（已选 {selected.size}）</span>
            <div className="flex flex-wrap gap-2">
              {isSetup ? (
                <>
                  <button
                    type="button"
                    className="btn-secondary h-8 px-3 text-xs disabled:opacity-50"
                    disabled={busy || !selected.size}
                    onClick={() => void handleAddToLibrary(false)}
                  >
                    加入引用库
                  </button>
                  <button
                    type="button"
                    className="btn-primary h-8 px-3 text-xs disabled:opacity-50"
                    disabled={busy || !selected.size}
                    onClick={() => void handleAddToLibrary(true)}
                  >
                    加入并同步参考文献章
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    className="text-xs font-medium text-violet-700 hover:underline disabled:opacity-50"
                    disabled={busy || !selected.size}
                    onClick={() => void handleAddToLibrary(false)}
                  >
                    仅加入引用库
                  </button>
                  <button
                    type="button"
                    className="btn-primary h-8 px-3 text-xs disabled:opacity-50"
                    disabled={busy || !selected.size}
                    onClick={() => void handleInsertSelected()}
                  >
                    插入选中
                  </button>
                </>
              )}
            </div>
          </div>
          <ul
            className={`space-y-2 overflow-y-auto pr-1 ${isSetup ? "max-h-[360px]" : "max-h-[280px]"}`}
          >
            {results.map((p) => {
              const k = literaturePaperKey(p);
              const checked = selected.has(k);
              const href = literaturePaperUrl(p);
              return (
                <li
                  key={k}
                  className={`flex gap-2 rounded-lg border p-2 text-xs transition ${
                    checked ? "border-violet-300 bg-violet-50/80" : "border-slate-100 bg-white/80"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="mt-1 shrink-0"
                    checked={checked}
                    onChange={() => toggle(p)}
                    aria-label={`选择：${p.title || "文献"}`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {p.source_label ? (
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-medium text-slate-600">
                          {p.source_label}
                        </span>
                      ) : null}
                      {href ? (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex min-w-0 flex-1 items-start gap-1 font-medium text-violet-800 hover:text-violet-950 hover:underline"
                          title="在新标签页打开文献"
                        >
                          <span className="line-clamp-2">{p.title || "（无标题）"}</span>
                          <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 opacity-70" aria-hidden />
                        </a>
                      ) : (
                        <span className="font-medium text-slate-800 line-clamp-2">{p.title || "（无标题）"}</span>
                      )}
                    </div>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {(p.authors?.slice(0, 3).join(", ") || "未知作者") +
                        (p.year ? ` · ${p.year}年` : "") +
                        (typeof p.citations === "number" && p.citations > 0
                          ? ` · 被引/星标 ${p.citations.toLocaleString()}`
                          : "")}
                      {p.journal ? ` · ${p.journal}` : ""}
                    </p>
                    {p.abstract_preview ? (
                      <p className="mt-1 line-clamp-3 text-[10px] leading-snug text-slate-600">
                        {p.abstract_preview}
                      </p>
                    ) : null}
                    {p.doi ? (
                      <a
                        href={`https://doi.org/${p.doi.replace(/^https?:\/\/doi\.org\//i, "")}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-0.5 block truncate text-[10px] text-violet-600 hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        DOI: {p.doi}
                      </a>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      <div className="border-t border-slate-100 pt-3">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">本书引用库</p>
        {savedLoading ? (
          <p className="mt-2 text-xs text-slate-500">加载中…</p>
        ) : saved.length === 0 ? (
          <p className="mt-2 text-xs text-slate-500">
            暂无已保存引用。上传含「参考文献」章节的 PDF 也会自动解析条目。
          </p>
        ) : (
          <ul className="mt-2 max-h-[160px] space-y-1.5 overflow-y-auto text-[11px] text-slate-600">
            {saved.map((c) => (
              <li key={c.id} className="rounded border border-slate-100 bg-white/70 px-2 py-1">
                <span className="font-medium text-slate-700">
                  {c.list_index != null ? `[${c.list_index}] ` : ""}
                  {c.title.slice(0, 80)}
                </span>
                <span className="block text-slate-400">
                  {c.source === "uploaded_file" ? "来自上传文件" : "来自检索"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
