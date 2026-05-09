import { ChevronLeft, ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import OutlineReviewPanel from "@/components/editor/OutlineReviewPanel";
import SetupView, { audienceKey, topicKey, type SetupViewActions } from "@/components/editor/SetupView";
import { setChapterGenMode, type ChapterGenMode } from "@/lib/chapterGenMode";
import type { Book } from "@/types/book";
import type { OutlineBookResponse } from "@/types/outline";

type Props = {
  book: Book;
  bookId: string;
  outline: OutlineBookResponse | undefined;
  outlineGeneratingUi: boolean;
  onPatchBook: (b: Book) => void;
  onGenerateOutline: (payload: { topic_override?: string | null; target_audience?: string | null }) => Promise<boolean>;
  onStartWriting: (mode: ChapterGenMode) => Promise<void>;
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
  /** 从 Step2「返回书稿设定」回到 Step1 时，右下角 FAB 仅为「保存设定」 */
  const [step1SaveOnlyFab, setStep1SaveOnlyFab] = useState(false);
  const [startMenuOpen, setStartMenuOpen] = useState(false);
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
    if (ok) {
      setStep1SaveOnlyFab(false);
      setWizardStep(2);
    }
  }

  async function handleFabSaveOnly() {
    try {
      await setupActionsRef.current?.saveMeta();
      setStep1SaveOnlyFab(false);
    } catch {
      /* toast in SetupView */
    }
  }

  const totalEst =
    outline?.chapters.reduce((s, c) => s + (c.estimated_words ?? 0), 0) ?? 0;

  return (
    <div className="planning-wizard relative min-h-full pb-16 pt-8 sm:pb-20">
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
              <h1 className="text-xl font-medium text-ink">{book.title || "未命名书稿"}</h1>
            </div>
          </div>
        </header>

        <StepIndicator step={wizardStep} />

        {wizardStep === 1 && (
          <>
            <SetupView book={book} onBookPatched={onPatchBook} onRegisterActions={(a) => (setupActionsRef.current = a)} />
            <div className="mt-12 flex justify-end border-t border-slate-100/90 pt-10">
              <button
                type="button"
                disabled={outlineGeneratingUi}
                onClick={() =>
                  step1SaveOnlyFab
                    ? void handleFabSaveOnly()
                    : void handleFabGenerate().catch(() => {
                        /* handled in parent */
                      })
                }
                className="btn-primary shadow-md"
              >
                {outlineGeneratingUi
                  ? "大纲生成中…"
                  : step1SaveOnlyFab
                    ? "保存设定"
                    : "保存并生成大纲 →"}
              </button>
            </div>
          </>
        )}

        {wizardStep === 2 && outline && (
          <OutlineReviewPanel
            mode="planning"
            book={book}
            bookId={bookId}
            outline={outline}
            outlineGeneratingUi={outlineGeneratingUi}
            onGenerateOutline={async () => {
              await onGenerateOutline({
                topic_override: window.localStorage.getItem(topicKey(bookId))?.trim() || null,
                target_audience: book.target_audience?.trim() || null,
              });
            }}
            onOutlinePatched={onOutlinePatched}
            onDeleteChapter={onDeleteChapter}
            onReorder={onReorder}
            dragDisabled={dragDisabled}
            collapsibleAside
            asideStorageKey={`planning_outline_aside_${bookId}`}
            leftAside={
              <>
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
                <button
                  type="button"
                  className="btn-secondary mt-4 w-full text-sm"
                  onClick={() => {
                    setStep1SaveOnlyFab(true);
                    setWizardStep(1);
                  }}
                >
                  ← 返回书稿设定
                </button>
              </>
            }
          />
        )}

        {wizardStep === 2 && outline && (
          <div className="mt-10 flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pb-12 pt-8 sm:pb-16">
            <button type="button" className="btn-primary text-sm" onClick={() => setWizardStep(3)}>
              确认大纲，进入下一步 →
            </button>
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
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center sm:items-center">
              <button type="button" className="btn-secondary w-full sm:w-auto" onClick={() => setWizardStep(2)}>
                ← 返回大纲
              </button>
              <div className="relative w-full sm:w-auto">
                <div className="flex w-full justify-center sm:inline-flex sm:w-auto">
                  <button
                    type="button"
                    className="btn-primary flex-1 rounded-r-none text-sm sm:flex-initial"
                    onClick={() => {
                      setChapterGenMode(bookId, "auto");
                      void onStartWriting("auto");
                    }}
                  >
                    ▶ 全部自动生成
                  </button>
                  <button
                    type="button"
                    className="btn-primary inline-flex min-w-[2.5rem] items-center justify-center rounded-l-none border-l border-white/25 px-2 text-sm"
                    aria-expanded={startMenuOpen}
                    aria-label="更多开始方式"
                    onClick={() => setStartMenuOpen((v) => !v)}
                  >
                    <ChevronDown className="h-4 w-4" />
                  </button>
                </div>
                {startMenuOpen ? (
                  <>
                    <div
                      className="fixed inset-0 z-[100] bg-transparent"
                      aria-hidden
                      onClick={() => setStartMenuOpen(false)}
                    />
                    <div className="absolute right-0 top-full z-[110] mt-1 min-w-[12rem] rounded-lg border border-slate-200 bg-white py-1 text-left text-sm shadow-lg">
                      <button
                        type="button"
                        className="block w-full px-3 py-2 text-left text-ink hover:bg-slate-50"
                        onClick={() => {
                          setStartMenuOpen(false);
                          setChapterGenMode(bookId, "auto");
                          void onStartWriting("auto");
                        }}
                      >
                        ▶ 全部自动生成
                      </button>
                      <button
                        type="button"
                        className="block w-full px-3 py-2 text-left text-ink hover:bg-slate-50"
                        onClick={() => {
                          setStartMenuOpen(false);
                          setChapterGenMode(bookId, "manual");
                          void onStartWriting("manual");
                        }}
                      >
                        ≡ 逐章手动生成
                      </button>
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
