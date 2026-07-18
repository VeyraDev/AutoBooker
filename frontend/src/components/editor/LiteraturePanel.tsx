import axios from "axios";
import { ExternalLink, Loader2, RefreshCw, Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";

import {
  loadLiteraturePanelState,
  saveLiteraturePanelState,
  useLiteratureSearchAbort,
} from "@/hooks/useLiteraturePanelState";

import {
  deleteCitationOccurrence,
  getCitationVerificationJob,
  listCitationOccurrences,
  listCitations,
  listCitationVerificationJobs,
  refreshCitationVerification,
  startCitationVerificationJob,
  weaveCitation,
  type CitationOccurrence,
} from "@/api/citations";
import { addSelectedLiterature, refineLiteratureQuery, searchLiterature } from "@/api/literature";
import type { CitationStyle } from "@/types/book";
import {
  literaturePaperKey,
  literaturePaperUrl,
  type CitationRecord,
  type CitationVerificationJob,
  type LiteraturePaper,
  type LiteratureTab,
} from "@/types/literature";
import { mergeLiteratureSelection } from "@/lib/literatureSelection";
import {
  CITATION_MANAGEMENT_VIEWS,
  citationSequenceLabel,
} from "@/lib/citationManagement";

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

/** 资料与引用：来源分类（与后端 source_registry 对齐的起步标签） */
const SOURCE_TYPE_FILTERS = [
  { id: "all", label: "全部" },
  { id: "paper", label: "论文" },
  { id: "book", label: "图书" },
  { id: "government", label: "政府/政策" },
  { id: "statistics", label: "统计数据" },
  { id: "industry_report", label: "行业报告" },
  { id: "newspaper", label: "报刊" },
  { id: "web", label: "普通网页" },
  { id: "user_material", label: "用户资料" },
] as const;

const BULK_VERIFY_CONFIRM_THRESHOLD = 50;

const VERIFICATION_META: Record<string, { label: string; className: string; hint: string }> = {
  verified: {
    label: "已核验",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
    hint: "外部来源匹配度高",
  },
  probable: {
    label: "基本匹配",
    className: "bg-sky-50 text-sky-700 border-sky-200",
    hint: "题名/作者/年份基本匹配",
  },
  user_uploaded_only: {
    label: "用户上传",
    className: "bg-slate-50 text-slate-600 border-slate-200",
    hint: "来自用户上传资料，尚未外部核验",
  },
  needs_verification: {
    label: "待核验",
    className: "bg-amber-50 text-amber-700 border-amber-200",
    hint: "缺少强外部匹配或关键元数据",
  },
  mismatch: {
    label: "疑似不匹配",
    className: "bg-red-50 text-red-700 border-red-200",
    hint: "外部匹配与当前条目存在明显差异",
  },
  unreachable: {
    label: "核验失败",
    className: "bg-zinc-50 text-zinc-700 border-zinc-200",
    hint: "外部核验暂时不可达，可稍后重试",
  },
};

function verificationMeta(citation: CitationRecord) {
  const status = citation.verification_status || (citation.metadata_status === "needs_completion" ? "needs_verification" : "");
  return (
    VERIFICATION_META[status] ?? {
      label: "未刷新",
      className: "bg-slate-50 text-slate-500 border-slate-200",
      hint: "尚未进行外部核验",
    }
  );
}

function verificationTimeLabel(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function jobStatusLabel(status: string): string {
  return {
    pending: "排队中",
    running: "进行中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
  }[status] ?? status;
}

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
  onPreviewInsert?: (payload: { sentence: string; node: Record<string, unknown> }) => void;
  onJumpToCitation?: (chapterIndex: number, nodeId: string) => void;
  onCitationDeleted?: (chapterIndex: number) => void;
  /** 助手工具注入的检索结果 */
  externalSearchResult?: import("@/types/literature").LiteratureSearchResult;
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
  onJumpToCitation,
  onCitationDeleted,
  externalSearchResult,
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
  const [sourceTypeFilter, setSourceTypeFilter] = useState<(typeof SOURCE_TYPE_FILTERS)[number]["id"]>("all");
  const [tabbed, setTabbed] = useState<Record<LiteratureTab, LiteraturePaper[]>>(emptyTabbed);
  const [refinedQueries, setRefinedQueries] = useState<string[]>([]);
  const [mustInclude, setMustInclude] = useState<string[]>([]);
  const [mustExclude, setMustExclude] = useState<string[]>([]);
  const [sourceHint, setSourceHint] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<CitationRecord[]>([]);
  const [savedLoading, setSavedLoading] = useState(false);
  const [savedSelected, setSavedSelected] = useState<Set<string>>(new Set());
  const [verifyingAll, setVerifyingAll] = useState(false);
  const [verifyingCitationIds, setVerifyingCitationIds] = useState<Set<string>>(new Set());
  const [verificationJob, setVerificationJob] = useState<CitationVerificationJob | null>(null);
  const [verificationJobs, setVerificationJobs] = useState<CitationVerificationJob[]>([]);
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<"search" | "manage">("search");
  const [occurrences, setOccurrences] = useState<CitationOccurrence[]>([]);

  const refreshSaved = useCallback(async () => {
    setSavedLoading(true);
    try {
      const [citations, used] = await Promise.all([
        listCitations(bookId),
        listCitationOccurrences(bookId).catch(() => []),
      ]);
      setSaved(citations);
      setOccurrences(used);
    } catch {
      setSaved([]);
    } finally {
      setSavedLoading(false);
    }
  }, [bookId]);

  const refreshVerificationJobs = useCallback(async () => {
    try {
      const jobs = await listCitationVerificationJobs(bookId);
      setVerificationJobs(jobs);
      const active = jobs.find((job) => ["pending", "running"].includes(job.status));
      if (active) {
        setVerificationJob(active);
        setVerifyingAll(true);
      }
    } catch {
      setVerificationJobs([]);
    }
  }, [bookId]);

  useEffect(() => {
    void refreshSaved();
  }, [refreshSaved]);

  useEffect(() => {
    if (view === "manage") {
      void refreshSaved();
      void refreshVerificationJobs();
    }
  }, [view, refreshSaved, refreshVerificationJobs]);

  useEffect(() => {
    if (!verificationJob || !["pending", "running"].includes(verificationJob.status)) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void getCitationVerificationJob(bookId, verificationJob.id)
        .then(async (job) => {
          if (cancelled) return;
          setVerificationJob(job);
          if (job.status === "completed") {
            setVerifyingAll(false);
            await refreshSaved();
            await refreshVerificationJobs();
            toast.success(`文献核验完成：成功 ${job.succeeded_count}，失败 ${job.failed_count}`);
          } else if (job.status === "failed" || job.status === "cancelled") {
            setVerifyingAll(false);
            toast.error(job.error_message || "文献核验任务未完成");
          }
        })
        .catch(() => {
          if (!cancelled) toast.error("读取文献核验进度失败");
        });
    }, 1500);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [bookId, refreshSaved, verificationJob]);

  useEffect(() => {
    if (defaultQuery.trim()) setQuery(defaultQuery.trim());
  }, [defaultQuery]);

  useEffect(() => {
    if (!externalSearchResult) return;
    setTabbed({
      papers: externalSearchResult.papers ?? [],
      github: externalSearchResult.github ?? [],
      wiki: externalSearchResult.wiki ?? [],
      official_docs: externalSearchResult.official_docs ?? [],
    });
    setRefinedQueries(externalSearchResult.refined_queries ?? []);
    setSourceHint(externalSearchResult.source_hint ?? "");
    setView("search");
  }, [externalSearchResult]);

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

  const results = (tabbed[tab] ?? []).filter((p) => {
    if (sourceTypeFilter === "all") return true;
    const src = String(p.source || p.source_label || "").toLowerCase();
    if (sourceTypeFilter === "paper") {
      return ["openalex", "crossref", "semantic_scholar", "arxiv", "paper"].some((k) => src.includes(k)) || tab === "papers";
    }
    if (sourceTypeFilter === "web") return src.includes("web") || tab === "wiki" || tab === "official_docs";
    if (sourceTypeFilter === "user_material") return src.includes("user");
    return src.includes(sourceTypeFilter);
  });

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

  async function handleAddToBook() {
    if (!selectedPapers.length) {
      toast.error("请先勾选文献");
      return;
    }
    setBusy(true);
    try {
      await addSelectedLiterature(bookId, selectedPapers);
      await refreshSaved();
      setSelected(new Set());
      const baseMsg = `已加入本书（${selectedPapers.length} 条）`;
      if (!citationStyle) {
        toast.success(`${baseMsg}。尚未选择引用格式，请先在书稿设定中选择。`, {
          duration: 5000,
        });
      } else {
        toast.success(baseMsg);
      }
    } catch {
      toast.error("加入本书失败");
    } finally {
      setBusy(false);
    }
  }

  function selectAllResults() {
    const keys = results.map((p) => literaturePaperKey(p));
    setSelected((prev) => mergeLiteratureSelection(prev, keys));
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

  function mergeVerifiedCitations(rows: CitationRecord[]) {
    const byId = new Map(rows.map((row) => [row.id, row]));
    setSaved((prev) => prev.map((row) => byId.get(row.id) ?? row));
  }

  async function handleRefreshOneCitation(citationId: string) {
    setVerifyingCitationIds((prev) => new Set(prev).add(citationId));
    try {
      const row = await refreshCitationVerification(bookId, citationId);
      mergeVerifiedCitations([row]);
      toast.success("已刷新文献核验");
    } catch {
      toast.error("刷新文献核验失败");
    } finally {
      setVerifyingCitationIds((prev) => {
        const next = new Set(prev);
        next.delete(citationId);
        return next;
      });
    }
  }

  async function startVerificationJob(citationIds?: string[], retryUnreachableOnly = false) {
    const job = await startCitationVerificationJob(bookId, citationIds, retryUnreachableOnly);
    setVerificationJob(job);
    await refreshVerificationJobs();
    return job;
  }

  async function handleRefreshCitationBatch() {
    if (!saved.length) return;
    const ids = [...savedSelected];
    if (!ids.length && saved.length > BULK_VERIFY_CONFIRM_THRESHOLD) {
      const ok = window.confirm(`将刷新 ${saved.length} 条本书文献的外部核验状态，可能需要较长时间。是否继续？`);
      if (!ok) return;
    }
    setVerifyingAll(true);
    try {
      const job = await startVerificationJob(ids.length ? ids : undefined);
      if (job.status === "completed") {
        setVerifyingAll(false);
        await refreshSaved();
        toast.success(`文献核验完成：成功 ${job.succeeded_count}，失败 ${job.failed_count}`);
      } else {
        toast.success(ids.length ? "已开始刷新已选文献核验" : "已开始刷新本书文献核验");
      }
    } catch {
      toast.error("批量刷新文献核验失败");
      setVerifyingAll(false);
    }
  }

  async function handleRetryFailedCitations() {
    if (!saved.some((citation) => citation.verification_status === "unreachable")) {
      toast.error("当前没有核验失败的文献");
      return;
    }
    setVerifyingAll(true);
    try {
      const job = await startVerificationJob(undefined, true);
      if (job.status === "completed") {
        setVerifyingAll(false);
        await refreshSaved();
        toast.success(`失败文献重试完成：成功 ${job.succeeded_count}，失败 ${job.failed_count}`);
      } else {
        toast.success("已开始重试核验失败文献");
      }
    } catch {
      toast.error("重试核验失败文献未能启动");
      setVerifyingAll(false);
    }
  }

  async function handleInsertFromLibrary() {
    if (!isSetup && !onPreviewInsert) return;
    const ids = [...savedSelected];
    if (!ids.length) {
      toast.error("请在引用管理中勾选要插入的文献");
      return;
    }
    setBusy(true);
    try {
      const inserts: { sentence: string; node: Record<string, unknown> }[] = [];
      for (const id of ids) {
        const { sentence, node } = await weaveCitation(bookId, id, chapterContext);
        if (sentence.trim()) inserts.push({ sentence: sentence.trim(), node });
      }
      if (!inserts.length) {
        toast.error("未能生成可插入句子");
        return;
      }
      inserts.forEach((payload) => onPreviewInsert?.(payload));
      toast.success("已插入引用");
      setSavedSelected(new Set());
    } catch {
      toast.error("生成引用句失败");
    } finally {
      setBusy(false);
    }
  }

  const hintText = sourceHint
    ? `当前检索来源：${sourceHint}。选择需要的文献并加入本书。`
    : isSetup
      ? "选择需要的文献并加入本书。"
      : "将文献加入本书后，可在引用管理中插入引用或生成引用句。";
  const citationHint = !citationStyle
    ? "尚未选择引用格式，请先在书稿设定中选择。"
    : null;

  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1 text-[11px]">
          {CITATION_MANAGEMENT_VIEWS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`rounded-md px-2 py-1.5 ${view === id ? "bg-white font-medium text-violet-800 shadow-sm" : "text-slate-500"}`}
              onClick={() => setView(id)}
            >
              {label}
            </button>
          ))}
      </div>
      {view === "search" ? (
      <>
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
          <div className="flex flex-wrap gap-1">
            {SOURCE_TYPE_FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                className={`rounded px-2 py-0.5 text-[10px] ${
                  sourceTypeFilter === f.id
                    ? "bg-slate-800 text-white"
                    : "border border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
                onClick={() => setSourceTypeFilter(f.id)}
              >
                {f.label}
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
                  onClick={() => void handleAddToBook()}
                >
                  加入本书
                </button>
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
                          ? ` · ${p.source === "github" ? "GitHub 星标" : "外部被引"} ${p.citations.toLocaleString()}`
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
      </>
      ) : null}

      {view === "manage" ? (
        <div className="space-y-3 border-t border-slate-100 pt-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">引用管理</p>
              <p className="mt-1 text-[10px] text-slate-500">
                书末参考文献将根据当前引用自动生成。
              </p>
            </div>
            {saved.length > 0 ? (
              <div className="flex flex-wrap items-center gap-2">
                {!isSetup ? (
                  <button
                    type="button"
                    className="text-[10px] text-violet-700 hover:underline"
                    onClick={selectAllSaved}
                  >
                    全选
                  </button>
                ) : null}
                <button
                  type="button"
                  className="btn-secondary flex h-8 items-center gap-1 px-2.5 text-xs disabled:opacity-50"
                  disabled={verifyingAll || savedLoading || !saved.length}
                  onClick={() => void handleRefreshCitationBatch()}
                  title={savedSelected.size ? "刷新已选文献的外部核验状态" : "刷新本书文献的外部核验状态"}
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${verifyingAll ? "animate-spin" : ""}`} aria-hidden />
                  {savedSelected.size ? "刷新已选核验" : "刷新全部核验"}
                </button>
                <button
                  type="button"
                  className="btn-secondary flex h-8 items-center gap-1 px-2.5 text-xs disabled:opacity-50"
                  disabled={verifyingAll || !saved.some((citation) => citation.verification_status === "unreachable")}
                  onClick={() => void handleRetryFailedCitations()}
                  title="只重试上次外部核验失败的文献"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${verifyingAll ? "animate-spin" : ""}`} aria-hidden />
                  重试失败核验
                </button>
                {!isSetup ? (
                  <button
                    type="button"
                    className="btn-primary h-8 px-3 text-xs disabled:opacity-50"
                    disabled={busy || !savedSelected.size}
                    onClick={() => void handleInsertFromLibrary()}
                    title="根据所选文献生成引用句并插入引用"
                  >
                    插入引用
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>

          {verificationJobs.length > 0 ? (
            <div className="rounded-md border border-slate-100 bg-slate-50/70 p-2">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[10px] font-medium text-slate-500">最近核验任务</p>
                <button
                  type="button"
                  className="text-[10px] text-violet-700 hover:underline"
                  onClick={() => void refreshVerificationJobs()}
                >
                  刷新记录
                </button>
              </div>
              <div className="mt-1 space-y-1">
                {verificationJobs.slice(0, 3).map((job) => (
                  <div
                    key={job.id}
                    className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-500"
                  >
                    <span>
                      {jobStatusLabel(job.status)} · {job.processed_count}/{job.total_count || "?"} · 成功{" "}
                      {job.succeeded_count} · 失败 {job.failed_count}
                    </span>
                    <span>{verificationTimeLabel(job.finished_at || job.created_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {verificationJob && ["pending", "running"].includes(verificationJob.status) ? (
            <div className="rounded-md border border-violet-100 bg-violet-50/70 p-2">
              <div className="flex items-center justify-between gap-3 text-[10px] text-violet-800">
                <span>文献核验中：{verificationJob.processed_count}/{verificationJob.total_count || "?"}</span>
                <span>
                  成功 {verificationJob.succeeded_count} · 失败 {verificationJob.failed_count}
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white">
                <div
                  className="h-full rounded-full bg-violet-600 transition-all"
                  style={{ width: `${Math.max(4, verificationJob.progress_pct)}%` }}
                />
              </div>
            </div>
          ) : null}

          {savedLoading ? (
            <p className="text-xs text-slate-500">加载中…</p>
          ) : saved.length === 0 ? (
            <p className="text-xs text-slate-500">暂无本书文献，请先在文献搜索中加入。</p>
          ) : (
            <div className="max-h-[560px] space-y-2 overflow-y-auto pr-1">
              {saved.map((citation) => {
                const checked = savedSelected.has(citation.id);
                const verifying = verifyingCitationIds.has(citation.id);
                const citationOccurrences = occurrences.filter(
                  (item) => item.citation_id === citation.id,
                );
                const used = citationOccurrences.length > 0;
                const complete =
                  citation.metadata_status === "complete" &&
                  citationOccurrences.every((item) => item.complete);
                const verification = verificationMeta(citation);
                const verifiedAt = verificationTimeLabel(citation.last_verified_at);
                return (
                  <article
                    key={citation.id}
                    className={`rounded-lg border p-2.5 text-xs ${
                      checked
                        ? "border-violet-300 bg-violet-50/70"
                        : "border-slate-100 bg-white"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {!isSetup ? (
                        <input
                          type="checkbox"
                          className="mt-1 shrink-0"
                          checked={checked}
                          onChange={() => toggleSaved(citation.id)}
                          aria-label={`选择：${citation.title}`}
                        />
                      ) : null}
                      <div className="min-w-0 flex-1">
                        <p className="font-medium leading-snug text-slate-700">
                          {citationSequenceLabel(citationStyle, citation.list_index)}
                          {citation.title}
                        </p>
                        <p className="mt-1 text-[10px] text-slate-500">
                          {citation.authors?.length
                            ? citation.authors.slice(0, 3).join("、")
                            : "未知作者"}
                          {citation.year ? ` · ${citation.year}` : ""}
                        </p>
                        <p className={`mt-1 text-[10px] ${used ? "text-violet-700" : "text-slate-400"}`}>
                          {used ? `正文引用 ${citationOccurrences.length} 处` : "尚未引用"}
                          {" · "}
                          {complete ? "文献信息完整" : "待补充文献信息"}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${verification.className}`}
                            title={verification.hint}
                          >
                            {verification.label}
                          </span>
                          <span className="text-[10px] text-slate-400">
                            {verifiedAt ? `刷新：${verifiedAt}` : verification.hint}
                          </span>
                          <button
                            type="button"
                            className="inline-flex items-center gap-1 text-[10px] text-violet-700 hover:underline disabled:text-slate-400 disabled:no-underline"
                            disabled={verifying || verifyingAll}
                            onClick={() => void handleRefreshOneCitation(citation.id)}
                            title="刷新该文献的外部核验状态"
                          >
                            <RefreshCw className={`h-3 w-3 ${verifying ? "animate-spin" : ""}`} aria-hidden />
                            刷新核验
                          </button>
                        </div>
                      </div>
                    </div>

                    {citationOccurrences.map((item) => (
                      <div
                        key={item.id}
                        className="ml-0 mt-2 rounded-md border border-slate-100 bg-slate-50/70 p-2 sm:ml-5"
                      >
                        <p className="text-[10px] font-medium text-slate-600">
                          第 {item.chapter_index} 章 · {item.chapter_title}
                        </p>
                        <p className="mt-1 line-clamp-3 text-[10px] leading-relaxed text-slate-500">
                          “{item.context_before}
                          {item.locator ? `〔${item.locator}〕` : "〔引用〕"}
                          {item.context_after}”
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-3">
                          <button
                            type="button"
                            className="text-[10px] text-violet-700 hover:underline"
                            onClick={() => onJumpToCitation?.(item.chapter_index, item.node_id)}
                          >
                            跳转正文
                          </button>
                          <button
                            type="button"
                            className="text-[10px] text-red-600 hover:underline"
                            onClick={() => {
                              void deleteCitationOccurrence(bookId, item.id)
                                .then(() => {
                                  onCitationDeleted?.(item.chapter_index);
                                  return refreshSaved();
                                })
                                .then(() => toast.success("已删除该次引用"))
                                .catch(() => toast.error("未能删除该次引用，请重试"));
                            }}
                          >
                            删除该次引用
                          </button>
                        </div>
                      </div>
                    ))}
                  </article>
                );
              })}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
