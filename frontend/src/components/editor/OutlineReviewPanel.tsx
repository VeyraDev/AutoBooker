import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useCallback, useState } from "react";
import { createPortal } from "react-dom";

import OutlineChapterListEditor from "@/components/editor/OutlineChapterListEditor";
import type { Book } from "@/types/book";
import type { OutlineBookResponse } from "@/types/outline";

export type OutlineReviewMode = "planning" | "review";

type Props = {
  mode: OutlineReviewMode;
  book: Book;
  bookId: string;
  outline: OutlineBookResponse;
  outlineGeneratingUi: boolean;
  onGenerateOutline?: () => void | Promise<unknown>;
  /** 全局大纲：将当前大纲章节同步到服务端（非书稿设定弹窗） */
  onSaveOutline?: () => void | Promise<unknown>;
  onOutlinePatched: () => void | Promise<void>;
  onDeleteChapter: (chapterIndex: number) => void | Promise<void>;
  onReorder: (items: { chapter_id: string; new_index: number }[]) => void | Promise<void>;
  dragDisabled: boolean;
  leftAside?: React.ReactNode;
  /** 左侧摘要可收起，收起后在视口左上角显示展开按钮 */
  collapsibleAside?: boolean;
  asideStorageKey?: string;
};

function CollapsibleAsideWrap({
  storageKey,
  children,
}: {
  storageKey: string;
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(storageKey) === "1";
    } catch {
      return false;
    }
  });

  const persist = useCallback(
    (next: boolean) => {
      setCollapsed(next);
      try {
        window.localStorage.setItem(storageKey, next ? "1" : "0");
      } catch {
        /* ignore */
      }
    },
    [storageKey],
  );

  if (!collapsed) {
    return (
      <aside className="outline-review-aside w-full shrink-0 lg:max-w-[min(100%,20rem)] sticky top-24 z-[2] h-fit max-h-[calc(100vh-7rem)] self-start overflow-y-auto rounded-xl border border-slate-200/80 bg-white/85 p-4 text-sm shadow-sm">
        <div className="mb-2 flex justify-end">
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            title="收起摘要栏"
            aria-label="收起摘要栏"
            onClick={() => persist(true)}
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>
        {children}
      </aside>
    );
  }

  if (typeof document === "undefined") return null;

  return createPortal(
    <button
      type="button"
      className="outline-aside-expand-btn fixed left-4 top-[5.5rem] z-[310] flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white/95 text-slate-600 shadow-md backdrop-blur-sm hover:bg-slate-50 hover:text-slate-900"
      title="展开书稿摘要"
      aria-label="展开书稿摘要"
      onClick={() => persist(false)}
    >
      <PanelLeftOpen className="h-5 w-5" />
    </button>,
    document.body,
  );
}

export default function OutlineReviewPanel({
  mode,
  book,
  bookId,
  outline,
  outlineGeneratingUi,
  onGenerateOutline,
  onSaveOutline,
  onOutlinePatched,
  onDeleteChapter,
  onReorder,
  dragDisabled,
  leftAside,
  collapsibleAside,
  asideStorageKey,
}: Props) {
  const totalEst = outline.chapters.reduce((s, c) => s + (c.estimated_words ?? 0), 0);

  const sk = asideStorageKey ?? `outline_aside_${bookId}_${mode}`;

  const asideNode =
    leftAside && collapsibleAside ? (
      <CollapsibleAsideWrap storageKey={sk}>{leftAside}</CollapsibleAsideWrap>
    ) : leftAside ? (
      <aside className="outline-review-aside w-full shrink-0 lg:max-w-[min(100%,20rem)] sticky top-24 z-[2] h-fit max-h-[calc(100vh-7rem)] self-start overflow-y-auto rounded-xl border border-slate-200/80 bg-white/85 p-4 text-sm shadow-sm">
        {leftAside}
      </aside>
    ) : null;

  return (
    <div className="outline-review-root mx-auto max-w-5xl px-1">
      <div
        className={`outline-review-body flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-start lg:gap-8 ${asideNode ? "" : "outline-review-body-single"}`}
      >
        {asideNode}

        <div className="outline-review-main min-w-0 flex-1">
          <div className="outline-review-header outline-review-header-tight flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-ink">{mode === "planning" ? "大纲预览" : "全局大纲"}</h2>
            <div className="flex flex-wrap items-center gap-2">
              {mode === "planning" ? (
                <button
                  type="button"
                  className="btn-secondary text-sm"
                  disabled={outlineGeneratingUi}
                  onClick={() => void onGenerateOutline?.()}
                >
                  {outlineGeneratingUi ? "生成中…" : "重新生成大纲"}
                </button>
              ) : onSaveOutline ? (
                <button type="button" className="btn-secondary text-sm" onClick={() => void onSaveOutline()}>
                  保存大纲
                </button>
              ) : null}
            </div>
          </div>

          <OutlineChapterListEditor
            bookId={bookId}
            outline={outline}
            onOutlinePatched={() => void onOutlinePatched()}
            onDeleteChapter={(idx) => void onDeleteChapter(idx)}
            onReorder={onReorder}
            dragDisabled={dragDisabled}
          />

          <p className="mt-4 text-xs text-slate-500">
            全书预估字数：{totalEst.toLocaleString()} 字
            {book.target_words ? (
              <span className="text-slate-400"> · 目标 {book.target_words.toLocaleString()} 字</span>
            ) : null}
          </p>
        </div>
      </div>
    </div>
  );
}
