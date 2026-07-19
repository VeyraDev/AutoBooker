import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";

import { addSourceSearchResults } from "@/api/sourceSearch";
import type { LiteraturePaper, SourceFacet, SourceType } from "@/types/literature";
import { literaturePaperKey, literaturePaperUrl } from "@/types/literature";

const SOURCE_LABELS: Record<SourceType, string> = {
  paper: "论文",
  book: "图书",
  news: "新闻/访谈",
  government: "政府/政策",
  industry_report: "行业报告",
  technical: "技术资料",
  web: "普通网页",
};

function asPapers(value: unknown): LiteraturePaper[] {
  if (!Array.isArray(value)) return [];
  return value.filter((x): x is LiteraturePaper => Boolean(x) && typeof x === "object" && "title" in (x as object));
}

function addErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data;
    if (detail && typeof detail === "object" && "detail" in detail) {
      const raw = (detail as { detail: unknown }).detail;
      if (typeof raw === "string" && raw.trim()) return raw;
    }
    if (error.response?.status === 500) return "服务器写入文献失败，请稍后重试";
    if (!error.response) return "无法连接服务器";
  }
  return error instanceof Error && error.message ? error.message : "加入失败";
}

/** Normalize authors for API: backend expects string[]. */
function sanitizePaper(p: LiteraturePaper): LiteraturePaper {
  const authors = Array.isArray(p.authors)
    ? p.authors.map((a) => String(a ?? "").trim()).filter(Boolean)
    : [];
  return {
    ...p,
    title: String(p.title || "").trim(),
    authors,
    year: p.year ?? null,
    source: p.source ?? null,
    url: p.url || undefined,
    doi: p.doi || undefined,
  };
}

export function normalizeSearchPayload(raw: Record<string, unknown> | null | undefined): Record<string, unknown> | null {
  if (!raw || typeof raw !== "object") return null;
  // Turn search_result wrapper → flat literature/person payload
  const nested = raw.result && typeof raw.result === "object" ? (raw.result as Record<string, unknown>) : null;
  const hasLit =
    nested &&
    (Array.isArray(nested.papers) ||
      Array.isArray(nested.wiki) ||
      Array.isArray(nested.github) ||
      Array.isArray(nested.official_docs) ||
      Array.isArray(nested.items));
  const base = hasLit ? nested! : raw;
  return {
    ...base,
    summary: raw.summary ?? base.summary,
    queries: raw.queries ?? base.refined_queries ?? base.queries,
    search_type: raw.search_type ?? base.search_type,
    raw_query: raw.raw_query ?? base.query,
    auto_ingested: raw.auto_ingested ?? false,
  };
}

type Props = {
  bookId: string;
  payload: Record<string, unknown>;
  compact?: boolean;
  onAdded?: () => void | Promise<void>;
};

export default function LiteratureSearchCard({ bookId, payload, compact, onAdded }: Props) {
  const data = useMemo(() => normalizeSearchPayload(payload) ?? payload, [payload]);
  const items = useMemo(() => {
    const modern = asPapers(data.items).filter((item) => item.source_type);
    if (modern.length) return modern;
    return [
      ...asPapers(data.papers).map((item) => ({ ...item, source_type: "paper" as const })),
      ...asPapers(data.books).map((item) => ({ ...item, source_type: "book" as const })),
      ...asPapers(data.news).map((item) => ({ ...item, source_type: "news" as const })),
      ...asPapers(data.government).map((item) => ({ ...item, source_type: "government" as const })),
      ...asPapers(data.industry_reports).map((item) => ({ ...item, source_type: "industry_report" as const })),
      ...[...asPapers(data.technical), ...asPapers(data.github), ...asPapers(data.official_docs)].map((item) => ({ ...item, source_type: "technical" as const })),
      ...[...asPapers(data.web), ...asPapers(data.wiki)].map((item) => ({ ...item, source_type: "web" as const })),
    ];
  }, [data]);
  const facets = (Array.isArray(data.facets) ? data.facets : []) as SourceFacet[];
  const sourceTypes = useMemo(
    () => Array.from(new Set(items.map((item) => item.source_type).filter(Boolean))) as SourceType[],
    [items],
  );
  const total = items.length;
  const isPerson = Boolean(data.person || data.candidates || data.works);
  const [tab, setTab] = useState<SourceType>("paper");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  const visibleList = useMemo(
    () => items.filter((item) => item.source_type === tab).slice(0, compact ? 20 : 40),
    [items, tab, compact],
  );
  const allPapers = items;

  useEffect(() => {
    setSelected(new Set());
    if (sourceTypes.length) setTab(sourceTypes[0]);
  }, [payload, sourceTypes.join("|")]);

  if (!total && !isPerson && !data.summary) return null;

  const queries = Array.isArray(data.queries) ? (data.queries as string[]) : [];

  function selectVisibleTab() {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const p of visibleList) next.add(literaturePaperKey(p));
      return next;
    });
  }

  function selectAllResults() {
    setSelected(new Set(allPapers.map((p) => literaturePaperKey(p))));
  }

  function clearSelection() {
    setSelected(new Set());
  }

  async function addSelected(target: "source_library" | "citation_library") {
    const picked = allPapers.filter((p) => selected.has(literaturePaperKey(p))).map(sanitizePaper);
    if (!picked.length) return;
    setBusy(true);
    try {
      const result = await addSourceSearchResults(bookId, target, picked);
      const label = target === "source_library" ? "资料库" : "文献库";
      toast.success(`已加入${label} ${result.added_count} 条${result.rejected.length ? `，拒绝 ${result.rejected.length} 条` : ""}`);
      setSelected(new Set());
      await onAdded?.();
    } catch (err) {
      toast.error(addErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={`mt-2 space-y-2 rounded-lg border border-teal-200 bg-teal-50/80 p-2.5 text-xs text-teal-950 ${
        compact ? "max-h-72 overflow-y-auto" : "max-h-[42vh] overflow-y-auto"
      }`}
    >
      <p className="font-medium text-teal-900">
        {total > 0 ? `资料搜索结果（${total}）` : `外部检索：${String(data.person ?? "")}`}
      </p>
      {data.summary ? <p className="text-[11px] text-teal-800">{String(data.summary)}</p> : null}
      {queries.length > 0 ? (
        <p className="text-[10px] text-teal-700">查询：{queries.slice(0, 4).join(" · ")}</p>
      ) : null}

      {total > 0 ? (
        <>
          <div className="flex flex-wrap gap-1">
            {sourceTypes.map((k) => (
              <button
                key={k}
                type="button"
                className={`rounded px-2 py-0.5 text-[10px] ${
                  tab === k ? "bg-teal-700 text-white" : "bg-white/90 text-teal-800"
                }`}
                onClick={() => setTab(k)}
              >
                {facets.find((facet) => facet.id === k)?.label ?? SOURCE_LABELS[k]} ({items.filter((item) => item.source_type === k).length})
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2 text-[10px]">
              <span className="text-teal-700">已选 {selected.size}</span>
              <button
                type="button"
                className="text-teal-800 underline-offset-2 hover:underline disabled:opacity-40"
                disabled={!visibleList.length}
                onClick={selectVisibleTab}
              >
                全选本页
              </button>
              <button
                type="button"
                className="text-teal-800 underline-offset-2 hover:underline disabled:opacity-40"
                disabled={!allPapers.length}
                onClick={selectAllResults}
              >
                全选全部
              </button>
              {selected.size > 0 ? (
                <button
                  type="button"
                  className="text-slate-500 underline-offset-2 hover:underline"
                  onClick={clearSelection}
                >
                  清空
                </button>
              ) : null}
            </div>
            <div className="flex gap-1">
              <button
                type="button"
                className="rounded border border-teal-600 bg-white px-2 py-1 text-[10px] text-teal-800 disabled:opacity-40"
                disabled={busy || selected.size === 0}
                onClick={() => void addSelected("source_library")}
              >
                加入资料库
              </button>
              <button
                type="button"
                className="rounded bg-teal-700 px-2 py-1 text-[10px] text-white disabled:opacity-40"
                disabled={busy || !allPapers.some((item) => selected.has(literaturePaperKey(item)) && item.citeability)}
                onClick={() => void addSelected("citation_library")}
              >
                {busy ? "加入中…" : "加入文献库"}
              </button>
            </div>
          </div>
          <ul className="space-y-1.5">
            {visibleList.length === 0 ? (
              <li className="text-[11px] text-teal-700">此分类暂无结果</li>
            ) : (
              visibleList.map((p) => {
                const key = literaturePaperKey(p);
                const url = literaturePaperUrl(p);
                return (
                  <li key={key} className="rounded border border-teal-200/70 bg-white/90 px-2 py-1.5">
                    <label className="flex cursor-pointer gap-2">
                      <input
                        type="checkbox"
                        className="mt-0.5"
                        checked={selected.has(key)}
                        onChange={() => {
                          setSelected((prev) => {
                            const next = new Set(prev);
                            if (next.has(key)) next.delete(key);
                            else next.add(key);
                            return next;
                          });
                        }}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="font-medium text-slate-800">{p.title}</span>
                        <span className="mt-0.5 block text-[10px] text-slate-500">
                          {(p.authors || []).slice(0, 3).join(", ")}
                          {p.year ? ` · ${p.year}` : ""}
                          {p.source_label || p.source ? ` · ${p.source_label || p.source}` : ""}
                        </span>
                        <span className={`mt-1 inline-block rounded px-1 py-0.5 text-[9px] ${p.citeability ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                          {p.citeability ? "可入文献库" : "仅作资料"}
                        </span>
                        {url ? (
                          <a
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[10px] text-teal-700 hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            打开
                          </a>
                        ) : null}
                      </span>
                    </label>
                  </li>
                );
              })
            )}
          </ul>
          <p className="text-[10px] text-teal-700">
            资料库保留摘要和来源元数据；只有元数据完整的论文、图书和报告可加入文献库。
          </p>
        </>
      ) : null}

      {isPerson && total === 0 && Array.isArray(data.works) ? (
        <ul className="max-h-40 space-y-1 overflow-y-auto">
          {(data.works as Array<{ title?: string; year?: number | string; source?: string }>)
            .slice(0, 20)
            .map((w, i) => (
              <li key={`${w.title}-${i}`} className="rounded bg-white/90 px-2 py-1 text-[11px]">
                {w.title}
                {w.year ? ` (${w.year})` : ""}
                {w.source ? ` · ${w.source}` : ""}
              </li>
            ))}
        </ul>
      ) : null}
    </div>
  );
}
