import { ChevronLeft } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import OutlineChapterListEditor from "@/components/editor/OutlineChapterListEditor";
import SetupView, { audienceKey, topicKey, type SetupViewActions } from "@/components/editor/SetupView";
import type { Book } from "@/types/book";
import type { OutlineBookResponse } from "@/types/outline";

type Props = {
  book: Book;
  bookId: string;
  outline: OutlineBookResponse | undefined;
  outlineGeneratingUi: boolean;
  onPatchBook: (b: Book) => void;
  onGenerateOutline: (payload: { topic_override?: string | null; target_audience?: string | null }) => Promise<boolean>;
  onStartWriting: () => Promise<void>;
  onOutlinePatched: () => void | Promise<void>;
  onReorder: (items: { chapter_id: string; new_index: number }[]) => void | Promise<void>;
  onDeleteChapter: (chapterIndex: number) => void | Promise<void>;
  dragDisabled: boolean;
};

function StepIndicator({ step }: { step: 1 | 2 | 3 }) {
  const items: { n: 1 | 2 | 3; label: string }[] = [
    { n: 1, label: "书稿设定" },
    { n: 2, label: "大纲预览" },
    { n: 3, label: "开始写作" },
  ];
  return (
    <div className="mb-10 flex flex-wrap items-center justify-center gap-2 text-sm">
      {items.map((it, i) => (
        <span key={it.n} className="flex items-center gap-2">
          {i > 0 ? <span className="text-slate-300">→</span> : null}
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 ${
              step === it.n ? "bg-brand/15 font-semibold text-brand-700 ring-1 ring-brand/30" : "text-slate-500"
            }`}
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white text-xs shadow-sm">{it.n}</span>
            {it.label}
          </span>
        </span>
      ))}
    </div>
  );
}

export default function PlanningWizard({
  book,
  bookId,
  outline,
  outlineGeneratingUi,
  onPatchBook,
  onGenerateOutline,
  onStartWriting,
  onOutlinePatched,
  onReorder,
  onDeleteChapter,
  dragDisabled,
}: Props) {
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const setupActionsRef = useRef<SetupViewActions | null>(null);

  useEffect(() => {
    if (outline && outline.chapters.length > 0 && book.status === "outline_ready") {
      setWizardStep((s) => (s === 1 ? 2 : s));
    }
  }, [book.status, outline?.chapters.length]);

  async function handleFabGenerate() {
    try {
      await setupActionsRef.current?.saveMeta();
    } catch {
      return;
    }
    const topic_override = window.localStorage.getItem(topicKey(bookId))?.trim() || null;
    const target_audience = window.localStorage.getItem(audienceKey(bookId))?.trim() || book.target_audience?.trim() || null;
    const ok = await onGenerateOutline({ topic_override, target_audience });
    if (ok) setWizardStep(2);
  }

  const totalEst =
    outline?.chapters.reduce((s, c) => s + (c.estimated_words ?? 0), 0) ?? 0;

  return (
    <div className="planning-wizard relative min-h-[calc(100vh-2rem)] px-4 pb-32 pt-8 sm:px-6">
      <div className="mx-auto max-w-[860px]">
        <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <Link
              to="/app/books"
              className="icon-button mt-0.5 h-10 w-10 shrink-0"
              aria-label="返回图书管理"
            >
              <ChevronLeft className="h-5 w-5" />
            </Link>
            <div>
              <nav className="text-xs text-slate-500">
                <Link to="/app/books" className="hover:text-brand-700">
                  图书管理
                </Link>
                <span className="mx-1.5 text-slate-300">/</span>
                <span className="font-medium text-slate-700">{book.title || "未命名"}</span>
                <span className="mx-1.5 text-slate-300">/</span>
                <span className="text-slate-600">策划</span>
              </nav>
              <h1 className="mt-1 text-xl font-medium text-ink">{book.title || "未命名书稿"}</h1>
            </div>
          </div>
        </header>

        <StepIndicator step={wizardStep} />

        {wizardStep === 1 && (
          <>
            <SetupView book={book} onBookPatched={onPatchBook} onRegisterActions={(a) => (setupActionsRef.current = a)} />
            <button
              type="button"
              disabled={outlineGeneratingUi}
              onClick={() =>
                void handleFabGenerate().catch(() => {
                  /* handled in parent */
                })
              }
              className="btn-primary fixed bottom-8 right-6 z-30 shadow-lg sm:right-10"
            >
              {outlineGeneratingUi ? "大纲生成中…" : "保存并生成大纲 →"}
            </button>
          </>
        )}

        {wizardStep === 2 && outline && (
          <div className="grid gap-6 lg:grid-cols-[minmax(200px,260px)_1fr]">
            <aside className="card h-fit border border-slate-200/80 bg-white/75 p-4 text-sm shadow-sm">
              <h3 className="font-semibold text-ink">书稿设定摘要</h3>
              <dl className="mt-3 space-y-2 text-slate-600">
                <div>
                  <dt className="text-xs text-slate-400">目标读者</dt>
                  <dd>{book.target_audience?.trim() || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-400">学科</dt>
                  <dd>{book.discipline?.trim() || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-400">目标字数</dt>
                  <dd>{book.target_words?.toLocaleString() ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-400">主题要点</dt>
                  <dd className="whitespace-pre-wrap text-xs leading-relaxed">
                    {window.localStorage.getItem(topicKey(bookId))?.trim() || "—"}
                  </dd>
                </div>
              </dl>
            </aside>
            <div className="min-w-0">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-ink">大纲预览</h2>
                <button
                  type="button"
                  className="btn-secondary text-sm"
                  disabled={outlineGeneratingUi}
                  onClick={() => {
                    const stored = window.localStorage.getItem(topicKey(bookId)) ?? "";
                    void onGenerateOutline({
                      topic_override: stored.trim() || null,
                      target_audience: book.target_audience?.trim() || null,
                    });
                  }}
                >
                  {outlineGeneratingUi ? "生成中…" : "重新生成大纲"}
                </button>
              </div>
              <OutlineChapterListEditor
                bookId={bookId}
                outline={outline}
                onOutlinePatched={() => void onOutlinePatched()}
                onDeleteChapter={(idx) => void onDeleteChapter(idx)}
                onReorder={onReorder}
                dragDisabled={dragDisabled}
              />
              <p className="mt-4 text-xs text-slate-500">全书预估字数：{totalEst.toLocaleString()} 字</p>
              <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-6">
                <button type="button" className="btn-secondary text-sm" onClick={() => setWizardStep(1)}>
                  ← 返回设定
                </button>
                <button type="button" className="btn-primary text-sm" onClick={() => setWizardStep(3)}>
                  确认大纲，进入下一步 →
                </button>
              </div>
            </div>
          </div>
        )}

        {wizardStep === 3 && (
          <div className="card mx-auto max-w-lg border border-slate-200/80 bg-white/85 p-8 text-center shadow-sm">
            <h2 className="text-lg font-semibold text-ink">准备进入写作</h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">
              确认后将进入写作工作台，系统将按章节顺序自动调用 AI 生成正文。您可随时在目录中查看进度或停止生成。
            </p>
            {outline ? (
              <p className="mt-4 text-xs text-slate-500">
                共 {outline.chapters.length} 章 · 预估 {totalEst.toLocaleString()} 字
              </p>
            ) : null}
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
              <button type="button" className="btn-secondary w-full sm:w-auto" onClick={() => setWizardStep(2)}>
                ← 返回大纲
              </button>
              <button type="button" className="btn-primary w-full sm:w-auto" onClick={() => void onStartWriting()}>
                确认大纲，开始写作 →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
