import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

import {
  confirmFormatStrategy,
  generateFormatStrategy,
  getFormatStrategy,
} from "@/features/outline/formatStrategyApi";
import type { ColumnSuggestion } from "@/types/formatStrategy";
import type { OutlineChapter } from "@/types/outline";

type Props = {
  bookId: string;
  chapters: OutlineChapter[];
  onConfirmed?: () => void;
};

function ColumnList({ title, items }: { title: string; items: ColumnSuggestion[] }) {
  if (!items.length) return null;
  return (
    <section className="mt-3">
      <p className="text-xs font-medium text-slate-500">{title}</p>
      <ul className="mt-1 space-y-1.5">
        {items.map((col) => (
          <li key={col.column_name} className="rounded border border-slate-100 bg-slate-50 p-2 text-xs">
            <div className="font-medium text-slate-800">{col.column_name}</div>
            {col.purpose ? <p className="mt-0.5 text-slate-600">{col.purpose}</p> : null}
            {col.appearance_condition ? (
              <p className="mt-0.5 text-slate-400">出现条件：{col.appearance_condition}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function FormatStrategyPanel({ bookId, chapters, onConfirmed }: Props) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);

  const query = useQuery({
    queryKey: ["format-strategy", bookId],
    queryFn: () => getFormatStrategy(bookId),
    retry: false,
  });

  useEffect(() => {
    if (!query.isError || busy) return;
    if (axios.isAxiosError(query.error) && query.error.response?.status === 404) {
      void (async () => {
        setBusy(true);
        try {
          await generateFormatStrategy(bookId);
          await qc.invalidateQueries({ queryKey: ["format-strategy", bookId] });
        } catch {
          /* 大纲刚生成时可能尚未就绪，用户可手动重试 */
        } finally {
          setBusy(false);
        }
      })();
    }
  }, [query.isError, query.error, bookId, qc, busy]);

  const strategy = query.data;

  async function handleRegenerate() {
    setBusy(true);
    try {
      await generateFormatStrategy(bookId, true);
      await qc.invalidateQueries({ queryKey: ["format-strategy", bookId] });
      toast.success("栏目策略已重新生成");
    } catch {
      toast.error("生成失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    setBusy(true);
    try {
      await confirmFormatStrategy(bookId);
      await qc.invalidateQueries({ queryKey: ["format-strategy", bookId] });
      toast.success("栏目策略已确认");
      onConfirmed?.();
    } catch {
      toast.error("确认失败");
    } finally {
      setBusy(false);
    }
  }

  if (query.isLoading || busy) {
    return <div className="mt-6 text-xs text-slate-500">加载体例与栏目…</div>;
  }

  if (!strategy) {
    return (
      <div className="mt-6 space-y-2">
        <p className="text-xs text-slate-500">尚未生成栏目策略</p>
        <button type="button" className="btn-secondary w-full text-xs" disabled={busy} onClick={() => void handleRegenerate()}>
          生成栏目策略
        </button>
      </div>
    );
  }

  const chapterEntries = chapters
    .map((ch) => ({
      chapter: ch,
      suggestions: strategy.chapter_suggestions?.[String(ch.index)] ?? [],
    }))
    .filter((row) => row.suggestions.length > 0);

  return (
    <div className="mt-6 border-t border-slate-100 pt-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold text-ink">体例与栏目</h3>
        <span className="text-xs text-slate-400">{strategy.status === "confirmed" ? "已确认" : "草稿"}</span>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">
        定义本书的阅读装置与条件栏目，不同章节可有差异。
      </p>

      <ColumnList title="书级固定栏目" items={strategy.book_level_columns ?? []} />
      <ColumnList title="条件栏目" items={strategy.conditional_columns ?? []} />

      {strategy.forbidden_patterns?.length ? (
        <section className="mt-3">
          <p className="text-xs font-medium text-slate-500">禁止模板化</p>
          <ul className="mt-1 list-inside list-disc text-xs text-slate-600">
            {strategy.forbidden_patterns.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {chapterEntries.length ? (
        <section className="mt-3">
          <p className="text-xs font-medium text-slate-500">逐章建议</p>
          <ul className="mt-1 space-y-2">
            {chapterEntries.map(({ chapter, suggestions }) => (
              <li key={chapter.id} className="text-xs text-slate-600">
                <span className="font-medium text-slate-700">
                  第{chapter.index}章 {chapter.title}
                </span>
                <span className="text-slate-400"> · {suggestions.map((s) => s.column_name).join(" · ")}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="mt-4 flex flex-col gap-2">
        <button type="button" className="btn-secondary w-full text-xs" disabled={busy} onClick={() => void handleRegenerate()}>
          重新生成
        </button>
        {strategy.status !== "confirmed" ? (
          <button type="button" className="btn-primary w-full text-xs" disabled={busy} onClick={() => void handleConfirm()}>
            确认栏目策略
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function useFormatStrategyConfirmed(bookId: string): boolean {
  const query = useQuery({
    queryKey: ["format-strategy", bookId],
    queryFn: () => getFormatStrategy(bookId),
    retry: false,
  });
  return query.data?.status === "confirmed";
}
