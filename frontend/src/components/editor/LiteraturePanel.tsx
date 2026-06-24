import axios from "axios";
import { ExternalLink, Loader2, Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";

import {
  loadLiteraturePanelState,
  saveLiteraturePanelState,
  useLiteratureSearchAbort,
} from "@/hooks/useLiteraturePanelState";

import { listCitations, syncBibliographyChapter, weaveCitation } from "@/api/citations";
import { addSelectedLiterature, refineLiteratureQuery, searchLiterature } from "@/api/literature";
import type { CitationStyle } from "@/types/book";
import {
  literaturePaperKey,
  literaturePaperUrl,
  type CitationRecord,
  type LiteraturePaper,
  type LiteratureTab,
} from "@/types/literature";

function isShortEnglishQuery(text: string): boolean {
  const q = text.trim();
  if (!q || /[\u4e00-\u9fff]/.test(q)) return false;
  return /^[A-Za-z0-9+_.# -]+$/.test(q) && q.split(/\s+/).length <= 3;
}

const TAB_LABELS: Record<LiteratureTab, string> = {
  papers: "论文",
  github: "GitHub",
  wiki: "百科",
  official_docs: "官方文档",
};

type Props = {
  bookId: string;
  citationStyle: CitationStyle | null;
  chapterIndex?: number;
  defaultQuery?: string;
  /** setup：设定页仅入库；editor：写作页可插入正文 */
  mode?: "setup" | "editor";
  /** 嵌入卡片时隐藏组件内小标题 */
  embedded?: boolean;
  /** 写作页：光标附近上下文，用于生成融入句 */
  chapterContext?: string;
  /** 预览后插入正文（叙述句，非 APA 标记） */
  onPreviewInsert?: (sentence: string) => void;
};

export default function LiteraturePanel({
  bookId,
  citationStyle,
  chapterIndex,
  defaultQuery = "",
  mode = "editor",
  embedded = false,
  chapterContext = "",
  onPreviewInsert,
}: Props) {
  const isSetup = mode === "setup";
  const persistMode = mode;
  const { begin: beginSearchAbort } = useLiteratureSearchAbort();
  const hydrated = useRef(false);
  const searchGen = useRef(0);

  const emptyTabbed = (): Record<LiteratureTab, LiteraturePaper[]> => ({
    papers: [],
    github: [],
    wiki: [],
    official_docs: [],
  });

  const [query, setQuery] = useState(defaultQuery);
  const [searching, setSearching] = useState(false);
  const [tab, setTab] = useState<LiteratureTab>("papers");
  const [tabbed, setTabbed] = useState<Record<LiteratureTab, LiteraturePaper[]>>(emptyTabbed);
  const [refinedQueries, setRefinedQueries] = useState<string[]>([]);
  const [mustInclude, setMustInclude] = useState<string[]>([]);
  const [mustExclude, setMustExclude] = useState<string[]>([]);
  const [sourceHint, setSourceHint] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<CitationRecord[]>([]);
  const [savedLoading, setSavedLoading] = useState(false);
  const [savedSelected, setSavedSelected] = useState<Set<string>>(new Set());
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

  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    const saved = loadLiteraturePanelState(bookId, persistMode);
    if (!saved) return;
    setQuery(saved.query);
    setTab(saved.tab);
    setTabbed(saved.tabbed);
    setRefinedQueries(saved.refinedQueries);
    setSourceHint(saved.sourceHint);
    setSelected(new Set(saved.selectedKeys));
  }, [bookId, persistMode]);

  useEffect(() => {
    if (!hydrated.current) return;
    saveLiteraturePanelState(bookId, persistMode, {
      query,
      tab,
      tabbed,
      refinedQueries,
      sourceHint,
      selectedKeys: [...selected],
    });
  }, [bookId, persistMode, query, tab, tabbed, refinedQueries, sourceHint, selected]);

  async function runRefine(scope: "book" | "chapter") {
    setSearching(true);
    try {
      const res = await refineLiteratureQuery(bookId, {
        scope,
        chapterIndex: scope === "chapter" ? chapterIndex : undefined,
        rawQuery: query.trim(),
      });
      setRefinedQueries(res.refined_queries);
      setMustInclude(res.must_include ?? []);
      setMustExclude(res.must_exclude ?? []);
      if (res.refined_queries.length && !isShortEnglishQuery(query)) {
        setQuery(res.refined_queries[0]);
      }
      toast.success("已生成检索词");
    } catch {
      toast.error("生成检索词失败");
    } finally {
      setSearching(false);
    }
  }

  async function runSearch() {
    const q = query.trim();
    if (!q && !refinedQueries.length) {
      toast.error("请输入检索词或先生成检索词");
      return;
    }
    const shortEn = isShortEnglishQuery(q);
    const gen = ++searchGen.current;
    setSearching(true);
    setSelected(new Set());
    setTabbed(emptyTabbed());
    const signal = beginSearchAbort();
    try {
      const res = await searchLiterature(bookId, {
        query: q,
        rows: 25,
        refined_queries: shortEn ? undefined : refinedQueries.length ? refinedQueries : undefined,
        must_include: shortEn ? undefined : mustInclude.length ? mustInclude : undefined,
        must_exclude: shortEn ? undefined : mustExclude.length ? mustExclude : undefined,
        skip_refine: shortEn || refinedQueries.length > 0,
        signal,
      });
      if (gen !== searchGen.current) return;
      setTabbed({
        papers: res.papers ?? [],
        github: res.github ?? [],
        wiki: res.wiki ?? [],
        official_docs: res.official_docs ?? [],
      });
      if (shortEn) {
        setRefinedQueries([]);
        setMustInclude([]);
        setMustExclude([]);
      } else {
        setRefinedQueries(res.refined_queries ?? refinedQueries);
      }
      setSourceHint(res.source_hint || "");
      const total =
        (res.papers?.length ?? 0) +
        (res.github?.length ?? 0) +
        (res.wiki?.length ?? 0) +
        (res.official_docs?.length ?? 0);
      if (res.warnings?.length) {
        toast(res.warnings[0], { icon: "⚠️", duration: 5000 });
      }
      if (!total) toast("未找到相关文献，可尝试英文关键词或换检索词");
      else {
        const gh = res.github?.length ?? 0;
        const parts = [
          `论文 ${res.papers?.length ?? 0}`,
          gh ? `GitHub ${gh}` : "",
          `百科 ${res.wiki?.length ?? 0}`,
          `文档 ${res.official_docs?.length ?? 0}`,
        ].filter(Boolean);
        toast.success(`检索完成：${parts.join(" · ")}${gh ? "（仓库见 GitHub 标签）" : ""}`);
        if (gh > 0 && shortEn) setTab("github");
      }
    } catch (err) {
      if (axios.isCancel(err)) return;
      if (axios.isAxiosError(err) && err.code === "ECONNABORTED") {
        toast.error("检索超时（约 3 分钟），请减少检索词或稍后重试");
      } else {
        toast.error("文献检索失败，请查看网络或稍后重试");
      }
    } finally {
      if (gen === searchGen.current) setSearching(false);
    }
  }

  const results = tabbed[tab] ?? [];

  function toggle(p: LiteraturePaper) {
    const k = literaturePaperKey(p);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  }

  const allPapers = [...tabbed.papers, ...tabbed.github, ...tabbed.wiki, ...tabbed.official_docs];
  const selectedPapers = allPapers.filter((p) => selected.has(literaturePaperKey(p)));

  async function handleAddToLibrary(syncBibliography = false) {
    if (!selectedPapers.length) {
      toast.error("请先勾选文献");
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
      const baseMsg = syncBibliography
        ? `已加入 ${selectedPapers.length} 条并同步书末参考文献章节`
        : `已加入引用库（${selectedPapers.length} 条）`;
      if (!citationStyle) {
        toast.success(`${baseMsg}。尚未设置引用格式，将暂按 APA 排版；可在书稿设定中修改。`, {
          duration: 5000,
        });
      } else {
        toast.success(baseMsg);
      }
    } catch {
      toast.error("加入引用库失败");
    } finally {
      setBusy(false);
    }
  }

  function selectAllResults() {
    const keys = results.map((p) => literaturePaperKey(p));
    setSelected(new Set(keys));
  }

  function clearResultSelection() {
    setSelected(new Set());
  }

  function toggleSaved(id: string) {
    setSavedSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAllSaved() {
    setSavedSelected(new Set(saved.map((c) => c.id)));
  }

  async function handleInsertFromLibrary() {
    if (!isSetup && !onPreviewInsert) return;
    const ids = [...savedSelected];
    if (!ids.length) {
      toast.error("请在下方引用库勾选要插入的文献");
      return;
    }
    setBusy(true);
    try {
      const sentences: string[] = [];
      for (const id of ids) {
        const { sentence } = await weaveCitation(bookId, id, chapterContext);
        if (sentence.trim()) sentences.push(sentence.trim());
      }
      if (!sentences.length) {
        toast.error("未能生成可插入句子");
        return;
      }
      onPreviewInsert?.(sentences.join("\n\n"));
      toast.success("已生成预览，请确认后应用");
      setSavedSelected(new Set());
    } catch {
      toast.error("生成融入句失败");
    } finally {
      setBusy(false);
    }
  }

  const hintText = sourceHint
    ? `当前书类检索源：${sourceHint}。检索后请「加入引用库」；在下方引用库中插入正文。`
    : isSetup
      ? "按书类自动选择检索源；勾选后加入本书引用库（自动解析摘录）。"
      : "检索后加入引用库；在下方本书引用库勾选并插入正文（叙述性援引，书目仅出现在参考文献章）。";
  const citationHint = !citationStyle
    ? "尚未设置引用格式，入库与排版将暂按 APA；可在书稿设定中修改。"
    : null;

  return (
    <div className="space-y-4 text-sm">
      <div className="space-y-2">
        {!embedded ? (
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">文献检索</p>
        ) : null}
        <p className="text-[11px] leading-relaxed text-slate-500">{hintText}</p>
        {citationHint ? (
          <p className="text-[11px] leading-relaxed text-amber-700">{citationHint}</p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {isSetup ? (
            <button
              type="button"
              className="btn-secondary h-9 px-3 text-xs"
              disabled={searching}
              onClick={() => void runRefine("book")}
            >
              生成检索词
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn-secondary h-9 px-3 text-xs"
                disabled={searching || chapterIndex == null}
                onClick={() => void runRefine("chapter")}
              >
                基于本章
              </button>
              <button
                type="button"
                className="btn-secondary h-9 px-3 text-xs"
                disabled={searching}
                onClick={() => void runRefine("book")}
              >
                基于全书
              </button>
            </>
          )}
        </div>
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
        {(refinedQueries.length > 0 || mustInclude.length > 0 || mustExclude.length > 0) ? (
          <div className="rounded-lg border border-slate-100 bg-slate-50/80 p-2 text-[10px] text-slate-600">
            {refinedQueries.length > 0 ? (
              <p className="mb-1">
                <span className="font-medium">检索词：</span>
                {refinedQueries.map((q) => (
                  <span key={q} className="mr-1 inline-block rounded bg-white px-1.5 py-0.5 border border-slate-200">
                    {q}
                  </span>
                ))}
              </p>
            ) : null}
            {mustInclude.length > 0 ? (
              <p className="mb-1">
                <span className="font-medium text-emerald-700">必须包含：</span>
                {mustInclude.join(" · ")}
              </p>
            ) : null}
            {mustExclude.length > 0 ? (
              <p>
                <span className="font-medium text-red-700">排除：</span>
                {mustExclude.join(" · ")}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      {(searching || tabbed.papers.length > 0 ||
        tabbed.github.length > 0 ||
        tabbed.wiki.length > 0 ||
        tabbed.official_docs.length > 0) ? (
        <div className="space-y-2">
          {searching ? (
            <p className="flex items-center gap-2 text-xs text-violet-600">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              检索中，请稍候…
            </p>
          ) : null}
          <div className="flex flex-wrap gap-1">
            {(Object.keys(TAB_LABELS) as LiteratureTab[]).map((k) => (
              <button
                key={k}
                type="button"
                className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${
                  tab === k ? "bg-violet-600 text-white" : "bg-slate-100 text-slate-600"
                }`}
                onClick={() => setTab(k)}
              >
                {TAB_LABELS[k]} ({tabbed[k].length})
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-slate-500">检索结果（已选 {selected.size}）</span>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="text-[10px] text-violet-700 hover:underline"
                disabled={!results.length}
                onClick={selectAllResults}
              >
                全选本页
              </button>
              {selected.size > 0 ? (
                <button
                  type="button"
                  className="text-[10px] text-slate-500 hover:underline"
                  onClick={clearResultSelection}
                >
                  清空
                </button>
              ) : null}
              <button
                type="button"
                className="btn-primary h-8 px-3 text-xs disabled:opacity-50"
                disabled={busy || !selected.size}
                onClick={() => void handleAddToLibrary(false)}
              >
                加入引用库
              </button>
              {isSetup ? (
                <button
                  type="button"
                  className="btn-secondary h-8 px-3 text-xs disabled:opacity-50"
                  disabled={busy || !selected.size}
                  onClick={() => void handleAddToLibrary(true)}
                >
                  并同步参考文献章
                </button>
              ) : null}
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
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">本书引用库</p>
          {!isSetup && saved.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="text-[10px] text-violet-700 hover:underline"
                onClick={selectAllSaved}
              >
                全选
              </button>
              <button
                type="button"
                className="btn-primary h-8 px-3 text-xs disabled:opacity-50"
                disabled={busy || !savedSelected.size}
                onClick={() => void handleInsertFromLibrary()}
              >
                插入正文
              </button>
            </div>
          ) : isSetup && saved.length > 0 ? (
            <button
              type="button"
              className="text-[10px] text-violet-700 hover:underline"
              onClick={selectAllSaved}
            >
              全选
            </button>
          ) : null}
        </div>
        {savedLoading ? (
          <p className="mt-2 text-xs text-slate-500">加载中…</p>
        ) : saved.length === 0 ? (
          <p className="mt-2 text-xs text-slate-500">
            暂无已保存引用。检索后加入此处；完整书目仅出现在书末参考文献章。
          </p>
        ) : (
          <ul className="mt-2 max-h-[200px] space-y-1.5 overflow-y-auto text-[11px] text-slate-600">
            {saved.map((c) => {
              const checked = savedSelected.has(c.id);
              return (
                <li
                  key={c.id}
                  className={`flex gap-2 rounded border px-2 py-1.5 ${
                    checked ? "border-violet-300 bg-violet-50/80" : "border-slate-100 bg-white/70"
                  }`}
                >
                  {!isSetup ? (
                    <input
                      type="checkbox"
                      className="mt-0.5 shrink-0"
                      checked={checked}
                      onChange={() => toggleSaved(c.id)}
                      aria-label={`选择：${c.title}`}
                    />
                  ) : null}
                  <div className="min-w-0 flex-1">
                    <span className="font-medium text-slate-700">
                      {c.list_index != null ? `[${c.list_index}] ` : ""}
                      {c.title.slice(0, 80)}
                    </span>
                    <span className="block text-slate-400">
                      {c.source === "uploaded_file" ? "来自上传文件" : "来自检索"}
                      {c.quotable_snippet ? " · 已解析摘录" : ""}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
