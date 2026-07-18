import { ChevronLeft, ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { Link } from "react-router-dom";
import OutlineReviewPanel from "@/components/editor/OutlineReviewPanel";
import SetupView, { type SetupViewActions } from "@/components/editor/SetupView";
import { setChapterGenMode, type ChapterGenMode } from "@/lib/chapterGenMode";
import type { Book } from "@/types/book";
import type { OutlineBookResponse } from "@/types/outline";

type Props = {
  book: Book;
  bookId: string;
  outline: OutlineBookResponse | undefined;
  /** 当前页是否正在等待 POST /outline 响应 */
  outlineRequestPending: boolean;
  outlineGeneratingUi: boolean;
  onPatchBook: (b: Book) => void;
  onGenerateOutline: (payload: {
    topic_override?: string | null;
    target_audience?: string | null;
    topic_brief?: string | null;
  }) => Promise<boolean>;
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
    <div className="mb-4 flex flex-wrap items-center justify-center gap-1.5 text-sm">
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
  outlineRequestPending,
  outlineGeneratingUi,
  onPatchBook,
  onGenerateOutline,
  onStartWriting,
  onOutlinePatched,
  onReorder,
  onDeleteChapter,
  dragDisabled,
}: Props) {
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(() => {
    if (
      book.status === "outline_ready" ||
      book.status === "outline_generating" ||
      (outline?.chapters.length ?? 0) > 0
    ) {
      return 2;
    }
    return 1;
  });
  /** 从 Step2「返回书稿设定」回到 Step1 时，右下角 FAB 仅为「保存设定」 */
  const [step1SaveOnlyFab, setStep1SaveOnlyFab] = useState(false);
  const [startMenuOpen, setStartMenuOpen] = useState(false);
  const [preparingOutline, setPreparingOutline] = useState(false);
  const setupActionsRef = useRef<SetupViewActions | null>(null);

  useEffect(() => {
    if (outline && outline.chapters.length > 0) {
      setWizardStep((s) => (s === 1 ? 2 : s));
    }
  }, [outline?.chapters.length]);

  useEffect(() => {
    if (book.status === "outline_generating" || book.status === "outline_ready") {
      setWizardStep((s) => (s === 1 ? 2 : s));
    }
  }, [book.status]);

  async function handleFabGenerate() {
    setPreparingOutline(true);
    try {
      if (!setupActionsRef.current) {
        toast.error("书稿设定尚未准备好，请刷新页面后重试");
        return;
      }
      const savedBook = await setupActionsRef.current.saveMeta();
      const ok = await onGenerateOutline({
        topic_override: null,
        target_audience: savedBook.target_audience?.trim() || null,
        topic_brief: savedBook.topic_brief?.trim() || null,
      });
      if (ok) {
        setStep1SaveOnlyFab(false);
        setWizardStep(2);
      }
    } finally {
      setPreparingOutline(false);
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
    <div className="planning-wizard relative min-h-full pb-12 pt-4 sm:pb-16">
      <div className="mx-auto max-w-[860px]">
        <header className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <Link
              to="/app/books"
              className="icon-button mt-0.5 h-10 w-10 shrink-0"
              aria-label="返回我的书稿"
            >
              <ChevronLeft className="h-5 w-5" />
            </Link>
            <div>
              <h1 className="text-xl font-medium text-ink">{book.title || "未命名书稿"}</h1>
            </div>
          </div>
        </header>

        <StepIndicator step={wizardStep} />

        {wizardStep === 1 && outlineGeneratingUi ? (
          <div className="card mb-4 border border-amber-200/80 bg-amber-50/80 p-4 text-center text-sm text-amber-900">
            正在生成大纲，完成后会自动显示。
          </div>
        ) : null}

        {wizardStep === 1 && (
          <>
            <SetupView
              book={book}
              onBookPatched={onPatchBook}
              onRegisterActions={(a) => (setupActionsRef.current = a)}
            />
            <div className="mt-12 flex justify-end border-t border-slate-100/90 pt-10">
              <button
                type="button"
                disabled={outlineRequestPending || preparingOutline}
                onClick={() => {
                  if (step1SaveOnlyFab) {
                    void handleFabSaveOnly();
                  } else {
                    void handleFabGenerate().catch(() => {
                      /* SetupView 与父组件负责错误提示 */
                    });
                  }
                }}
                className="btn-primary shadow-md"
              >
                {outlineGeneratingUi
                  ? "正在生成大纲…"
                  : preparingOutline
                    ? "正在保存设定…"
                  : book.status === "outline_generating"
                    ? "重新生成大纲 →"
                    : step1SaveOnlyFab
                      ? "保存设定"
                      : "生成大纲"}
              </button>
            </div>
          </>
        )}

        {wizardStep === 2 && outlineGeneratingUi ? (
          <div className="card border border-slate-200/80 bg-white/85 p-10 text-center text-sm text-slate-600">
            <p className="font-medium text-ink">正在生成大纲…</p>
            <p className="mt-2 text-xs text-slate-500">正在规划章节结构。</p>
          </div>
        ) : null}

        {wizardStep === 2 && !outlineGeneratingUi && outline && outline.chapters.length > 0 && (
          <OutlineReviewPanel
            mode="planning"
            book={book}
            bookId={bookId}
            outline={outline}
            outlineGeneratingUi={false}
            onGenerateOutline={async () => {
              const ok = await onGenerateOutline({
                topic_override: null,
                target_audience: book.target_audience?.trim() || null,
                topic_brief: book.topic_brief?.trim() || null,
              });
              if (ok) setWizardStep(2);
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
                    <dd>
                      {book.disciplines?.length
                        ? book.disciplines.join("、")
                        : book.discipline?.trim() || "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">目标字数</dt>
                    <dd>{book.target_words?.toLocaleString() ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400">主题要点</dt>
                    <dd className="whitespace-pre-wrap text-xs leading-relaxed">
                      {book.topic_brief?.trim() || "—"}
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

        {wizardStep === 2 && !outlineGeneratingUi && outline && outline.chapters.length > 0 && (
          <div className="mt-10 flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pb-12 pt-8 sm:pb-16">
            <button
              type="button"
              className="btn-primary text-sm"
              onClick={() => setWizardStep(3)}
            >
              确认大纲
            </button>
          </div>
        )}

        {wizardStep === 3 && (
          <div className="card mx-auto max-w-lg border border-slate-200/80 bg-white/85 p-8 text-center shadow-sm">
            <h2 className="text-lg font-semibold text-ink">选择写作方式</h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">
              系统将按章节顺序生成正文，你可以随时查看或暂停。
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
                    自动生成全书
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
                        自动生成全书
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
                        逐章生成
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
