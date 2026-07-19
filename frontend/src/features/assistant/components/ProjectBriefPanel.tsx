import { useState } from "react";
import toast from "react-hot-toast";

import {
  undoQuickFill,
  type ExtractedRequirement,
  type SettingOrigin,
} from "@/features/assistant/api/assistantApi";
import { BOOK_TYPE_LABEL } from "@/features/assistant/bookSettingsSpec";
import type { IntakeState } from "@/features/intake/api/intakeApi";
import { STYLE_LABELS } from "@/lib/styleTypes";
import type { Book, StyleType } from "@/types/book";

type Props = {
  book: Book | null | undefined;
  intake: IntakeState | null | undefined;
  loading?: boolean;
  proceeding?: boolean;
  settingOrigins?: Record<string, SettingOrigin>;
  confirmedRequirements?: ExtractedRequirement[];
  quickFillOpId?: string | null;
  onProceed: () => void;
  onOpenAdvanced: () => void;
  onBookUpdated?: (book: Book) => void;
};

const ORIGIN_LABEL: Record<string, string> = {
  user_explicit: "用户提供",
  user_manual: "用户手动修改",
  assistant_inferred: "助手建议",
  system_default: "系统默认",
};

function originHint(origins: Record<string, SettingOrigin> | undefined, key: string): string | null {
  const o = origins?.[key]?.origin;
  if (!o) return null;
  return ORIGIN_LABEL[o] ?? o;
}

export default function ProjectBriefPanel({
  book,
  intake,
  loading,
  proceeding,
  settingOrigins,
  confirmedRequirements = [],
  quickFillOpId,
  onProceed,
  onOpenAdvanced,
  onBookUpdated,
}: Props) {
  const [undoing, setUndoing] = useState(false);

  if (loading) {
    return <div className="p-4 text-sm text-slate-500">加载项目信息…</div>;
  }

  const goal = intake?.raw_goal_text?.trim() || "（尚未填写创作意图）";
  const styleLabel =
    book?.style_type && book.style_type in STYLE_LABELS
      ? STYLE_LABELS[book.style_type as StyleType]
      : book?.style_type || "—";

  const pendingStyle = book?.pending_writing_spec?.field === "style_type"
    ? book.pending_writing_spec
    : null;
  const bookRows: { key: string; label: string; value: string; warning?: string }[] = [
    { key: "title", label: "书名", value: book?.title?.trim() || "—" },
    {
      key: "book_type",
      label: "一级分类",
      value: book?.book_type ? BOOK_TYPE_LABEL[book.book_type] ?? book.book_type : "—",
    },
    {
      key: "style_type",
      label: "二级体裁",
      value: styleLabel,
      warning: pendingStyle
        ? `识别到“${pendingStyle.requested_label || pendingStyle.requested_value}”，当前写作路由尚未支持，未自动覆盖。`
        : undefined,
    },
    { key: "target_audience", label: "目标读者", value: book?.target_audience?.trim() || "—" },
    {
      key: "disciplines",
      label: "学科领域",
      value:
        (book?.disciplines?.length ? book.disciplines.join("、") : book?.discipline?.trim()) || "—",
    },
    {
      key: "target_words",
      label: "目标字数",
      value: book?.target_words != null ? book.target_words.toLocaleString() : "—",
    },
    {
      key: "topic_tags",
      label: "话题标签",
      value: book?.topic_tags?.length ? book.topic_tags.join(" · ") : "—",
    },
    { key: "topic_brief", label: "主题要点", value: book?.topic_brief?.trim() || "—" },
    { key: "citation_style", label: "引用格式", value: book?.citation_style || "—" },
  ];

  async function handleUndo() {
    if (!book?.id) return;
    setUndoing(true);
    try {
      const res = await undoQuickFill(book.id, quickFillOpId);
      if (res.book_settings && onBookUpdated) {
        onBookUpdated({ ...book, ...(res.book_settings as Partial<Book>) } as Book);
      } else {
        onBookUpdated?.(book);
      }
      toast.success("已撤销本次快速补齐");
    } catch {
      toast.error("撤销失败");
    } finally {
      setUndoing(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 px-3 py-2">
        <h3 className="text-sm font-semibold text-slate-800">书稿设定</h3>
        <p className="text-xs text-slate-500">唯一正式设定；与高级编辑同一份字段</p>
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
            <p className="text-xs font-medium text-slate-500">正式设定</p>
            {quickFillOpId ? (
              <button
                type="button"
                className="rounded border border-slate-200 px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                disabled={undoing || proceeding}
                onClick={() => void handleUndo()}
              >
                {undoing ? "撤销中…" : "撤销本次补齐"}
              </button>
            ) : null}
          </div>
          <dl className="space-y-2">
            {bookRows.map((row) => {
              const hint = originHint(settingOrigins, row.key);
              return (
                <div key={row.key}>
                  <dt className="text-[11px] text-slate-400">
                    {row.label}
                    {hint ? <span className="ml-1 text-slate-300">· {hint}</span> : null}
                  </dt>
                  <dd className="mt-0.5 whitespace-pre-wrap text-slate-700">{row.value}</dd>
                  {row.warning ? (
                    <p className="mt-1 text-[11px] leading-relaxed text-amber-700">{row.warning}</p>
                  ) : null}
                </div>
              );
            })}
          </dl>
        </section>

        {confirmedRequirements.length > 0 ? (
          <section className="space-y-2 border-t border-slate-100 pt-3">
            <p className="text-xs font-medium text-slate-500">已提取要求</p>
            <ul className="list-inside list-disc space-y-1 text-slate-700">
              {confirmedRequirements.map((r) => (
                <li key={`${r.category}-${r.content.slice(0, 40)}`}>{r.content}</li>
              ))}
            </ul>
          </section>
        ) : null}

        <p className="text-xs leading-relaxed text-slate-400">
          用对话区「快速补齐」集中判断设定；需要手改时用「高级编辑」。
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
          {proceeding ? "生成中…" : "生成大纲"}
        </button>
      </div>
    </div>
  );
}
