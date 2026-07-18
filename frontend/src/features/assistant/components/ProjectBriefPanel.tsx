import { useState } from "react";
import toast from "react-hot-toast";

import { inferBookSetup } from "@/api/books";
import type { WritingBasis } from "@/features/assistant/api/assistantApi";
import {
  BASIS_SETUP_FIELDS,
  BOOK_TYPE_LABEL,
} from "@/features/assistant/bookSettingsSpec";
import type { IntakeState } from "@/features/intake/api/intakeApi";
import { STYLE_LABELS } from "@/lib/styleTypes";
import type { Book, StyleType } from "@/types/book";

type Props = {
  book: Book | null | undefined;
  intake: IntakeState | null | undefined;
  basis?: WritingBasis | null;
  loading?: boolean;
  proceeding?: boolean;
  onProceed: () => void;
  onOpenAdvanced: () => void;
  onBookUpdated?: (book: Book) => void;
};

function basisText(basis: WritingBasis | null | undefined, key: string): string {
  const v = basis?.[key as keyof WritingBasis];
  return typeof v === "string" ? v.trim() : "";
}

function basisList(basis: WritingBasis | null | undefined, key: string): string[] {
  const v = basis?.[key as keyof WritingBasis];
  return Array.isArray(v) ? v.map((x) => String(x).trim()).filter(Boolean) : [];
}

export default function ProjectBriefPanel({
  book,
  intake,
  basis,
  loading,
  proceeding,
  onProceed,
  onOpenAdvanced,
  onBookUpdated,
}: Props) {
  const [inferring, setInferring] = useState(false);

  if (loading) {
    return <div className="p-4 text-sm text-slate-500">加载项目信息…</div>;
  }

  const goal = intake?.raw_goal_text?.trim() || "（尚未填写创作意图）";
  const styleLabel =
    book?.style_type && book.style_type in STYLE_LABELS
      ? STYLE_LABELS[book.style_type as StyleType]
      : book?.style_type || "—";

  const bookRows: { label: string; value: string }[] = [
    { label: "书名", value: book?.title?.trim() || "—" },
    {
      label: "一级分类",
      value: book?.book_type ? BOOK_TYPE_LABEL[book.book_type] ?? book.book_type : "—",
    },
    { label: "二级体裁", value: styleLabel },
    { label: "目标读者", value: book?.target_audience?.trim() || "—" },
    {
      label: "学科领域",
      value:
        (book?.disciplines?.length ? book.disciplines.join("、") : book?.discipline?.trim()) || "—",
    },
    {
      label: "目标字数",
      value: book?.target_words != null ? book.target_words.toLocaleString() : "—",
    },
    {
      label: "话题标签",
      value: book?.topic_tags?.length ? book.topic_tags.join(" · ") : "—",
    },
    { label: "主题要点", value: book?.topic_brief?.trim() || "—" },
    { label: "引用格式", value: book?.citation_style || "—" },
  ];

  async function handleInfer() {
    if (!book?.id) return;
    setInferring(true);
    const toastId = toast.loading("正在根据创作意图补齐设定…");
    try {
      const next = await inferBookSetup(book.id);
      onBookUpdated?.(next);
      toast.success("已补齐类型、体裁、标签与主题要点等", { id: toastId });
    } catch {
      toast.error("补齐失败，请稍后重试", { id: toastId });
    } finally {
      setInferring(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 px-3 py-2">
        <h3 className="text-sm font-semibold text-slate-800">项目要点</h3>
        <p className="text-xs text-slate-500">与高级编辑使用同一套书稿设定</p>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">
        <section>
          <p className="text-xs font-medium text-slate-500">创作意图</p>
          <p className="mt-1 whitespace-pre-wrap rounded border border-slate-100 bg-slate-50 p-2 text-slate-700">
            {goal}
          </p>
        </section>
        {intake?.negative_constraints_text ? (
          <section>
            <p className="text-xs font-medium text-slate-500">要避免的写法</p>
            <p className="mt-1 whitespace-pre-wrap text-slate-600">{intake.negative_constraints_text}</p>
          </section>
        ) : null}

        <section className="space-y-2 border-t border-slate-100 pt-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium text-slate-500">书稿设定</p>
            <button
              type="button"
              className="rounded border border-slate-200 px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              disabled={inferring || proceeding || !goal || goal.startsWith("（尚未")}
              onClick={() => void handleInfer()}
            >
              {inferring ? "补齐中…" : "智能补齐设定"}
            </button>
          </div>
          <dl className="space-y-2">
            {bookRows.map((row) => (
              <div key={row.label}>
                <dt className="text-[11px] text-slate-400">{row.label}</dt>
                <dd className="mt-0.5 whitespace-pre-wrap text-slate-700">{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="space-y-2 border-t border-slate-100 pt-3">
          <p className="text-xs font-medium text-slate-500">策划细节（助手整理）</p>
          {BASIS_SETUP_FIELDS.map((f) => {
            const list = "list" in f && f.list ? basisList(basis, f.key) : [];
            const text = "list" in f && f.list ? "" : basisText(basis, f.key);
            const empty = "list" in f && f.list ? list.length === 0 : !text;
            return (
              <div key={f.key}>
                <p className="text-[11px] text-slate-400">{f.label}</p>
                {"list" in f && f.list ? (
                  empty ? (
                    <p className="mt-0.5 text-slate-400">—</p>
                  ) : (
                    <ul className="mt-0.5 list-inside list-disc text-slate-700">
                      {list.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  )
                ) : (
                  <p className={`mt-0.5 whitespace-pre-wrap ${empty ? "text-slate-400" : "text-slate-700"}`}>
                    {text || "—"}
                  </p>
                )}
              </div>
            );
          })}
        </section>

        <p className="text-xs leading-relaxed text-slate-400">
          「智能补齐设定」会按创作意图重判一级分类与二级体裁（新建时的大众非虚构只是占位）。也可在「高级编辑」里手动改。
        </p>
      </div>
      <div className="space-y-2 border-t border-slate-200 p-3">
        <button type="button" className="btn-secondary w-full text-sm" onClick={onOpenAdvanced}>
          高级编辑
        </button>
        <button
          type="button"
          className="btn-primary w-full text-sm disabled:opacity-50"
          disabled={proceeding || !goal || goal.startsWith("（尚未")}
          onClick={onProceed}
        >
          {proceeding ? "正在生成大纲…" : "生成大纲"}
        </button>
      </div>
    </div>
  );
}
