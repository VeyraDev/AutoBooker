import { BookOpen, ClipboardList, GraduationCap, MessageSquareText, PenLine, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

import type { LlmModelsResponse } from "@/api/config";
import { searchReferences } from "@/api/references";
import AiAssistantPanel from "@/components/editor/AiAssistantPanel";
import type { EditorAiPreviewPayload } from "@/types/aiPreview";
import LiteraturePanel from "@/components/editor/LiteraturePanel";
import ReviewPanel from "@/components/editor/ReviewPanel";
import type { AutoSaveUi } from "@/components/editor/EditorTopBar";
import type { CitationStyle } from "@/types/book";
import type { OutlineChapter } from "@/types/outline";
import type { LiteratureQuoteBlock } from "@/types/literature";

export type RightPanelTab = "detail" | "refs" | "literature" | "ai" | "review";

type Props = {
  bookId: string;
  onClose: () => void;
  activeChapter: OutlineChapter | null;
  autoSaveStatus: AutoSaveUi;
  savedAt: Date | null;
  aiModel: string | null;
  llmCatalog?: LlmModelsResponse;
  llmCatalogLoading?: boolean;
  onModelChange: (model: string) => void;
  /** 由 BubbleMenu「…」联动打开时切换到 AI 并预填选区 */
  activeTab: RightPanelTab;
  onTabChange: (t: RightPanelTab) => void;
  assistantSeed: string;
  onConsumeAssistantSeed: () => void;
  citationStyle?: CitationStyle | null;
  /** 参考资料插入到编辑器 */
  onInsertReference?: (plain: string, filename: string) => void;
  /** 文献引用段落插入正文（含标记与摘录） */
  onInsertLiteratureQuotes?: (quotes: LiteratureQuoteBlock[]) => void;
  chapterIndex?: number | null;
  editorSelectionText?: string;
  chapterContext?: string;
  onApplyReviewFix?: (quote: string, suggestion: string) => void;
  onAiPreviewReady?: (payload: EditorAiPreviewPayload) => void;
  quotedFigureId?: string | null;
  quotedFigureAnnotation?: string;
  onClearFigureQuote?: () => void;
  onFigureReady?: (payload: {
    figure_id: string;
    file_url: string | null;
    figure_number: string | null;
    status: string;
    caption: string | null;
    figure_type: string;
  }) => void;
  /** 打开全局大纲以编辑章节元信息 */
  onOpenOutlineEditor?: () => void;
};

export default function RightPanel({
  bookId,
  onClose,
  activeChapter,
  autoSaveStatus,
  savedAt,
  aiModel,
  llmCatalog,
  llmCatalogLoading,
  onModelChange,
  activeTab,
  onTabChange,
  assistantSeed,
  onConsumeAssistantSeed,
  citationStyle = null,
  onInsertReference,
  onInsertLiteratureQuotes,
  chapterIndex = null,
  editorSelectionText = "",
  chapterContext = "",
  onApplyReviewFix,
  onAiPreviewReady,
  quotedFigureId = null,
  quotedFigureAnnotation = "",
  onClearFigureQuote,
  onFigureReady,
  onOpenOutlineEditor,
}: Props) {
  const [refHits, setRefHits] = useState<{ content: string; filename: string }[]>([]);
  const [refsLoading, setRefsLoading] = useState(false);

  useEffect(() => {
    if (activeTab !== "refs" || !activeChapter?.title?.trim()) {
      setRefHits([]);
      return;
    }
    setRefsLoading(true);
    searchReferences(bookId, { query: activeChapter.title.trim(), top_k: 5 })
      .then((r) => setRefHits(r.hits ?? []))
      .catch(() => setRefHits([]))
      .finally(() => setRefsLoading(false));
  }, [activeTab, bookId, activeChapter?.title]);

  function tabBtn(id: RightPanelTab, icon: React.ReactNode, label: string) {
    return (
      <button
        key={id}
        type="button"
        className={`right-panel-tab ${activeTab === id ? "right-panel-tab-active" : ""}`}
        title={label}
        aria-label={label}
        aria-pressed={activeTab === id}
        onClick={() => onTabChange(id)}
      >
        {icon}
      </button>
    );
  }

  return (
    <aside className="right-panel" aria-label="辅助面板">
      <div className="right-panel-tab-bar">
        {tabBtn("detail", <ClipboardList className="h-4 w-4" aria-hidden />, "章节细则")}
        {tabBtn("refs", <BookOpen className="h-4 w-4" aria-hidden />, "资料片段")}
        {tabBtn("literature", <GraduationCap className="h-4 w-4" aria-hidden />, "文献搜索")}
        {tabBtn("ai", <MessageSquareText className="h-4 w-4" aria-hidden />, "AI 助手")}
        {tabBtn("review", <ShieldCheck className="h-4 w-4" aria-hidden />, "审阅")}
        <button
          type="button"
          className="right-panel-tab ml-auto max-w-[44px] flex-none text-slate-500 hover:text-slate-800"
          title="关闭"
          aria-label="关闭辅助面板"
          onClick={onClose}
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>

      <div className="right-panel-inner">
        {activeTab === "detail" && (
          <div className="space-y-3 text-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">章节细则</p>
            {activeChapter ? (
              <>
                <p className="font-medium text-ink">{activeChapter.title}</p>
                <p className="text-xs text-slate-500">
                  字数 {activeChapter.word_count ?? 0} · 预估 {activeChapter.estimated_words ?? 0}
                </p>
                <p className="leading-relaxed text-slate-600">{activeChapter.summary || "暂无摘要"}</p>
                {activeChapter.key_points?.length ? (
                  <ul className="list-disc space-y-1 pl-4 text-xs text-slate-600">
                    {activeChapter.key_points.map((k) => (
                      <li key={k}>{k}</li>
                    ))}
                  </ul>
                ) : null}
                <button
                  type="button"
                  className="text-xs font-medium text-violet-700 hover:underline"
                  onClick={() => {
                    onOpenOutlineEditor?.();
                    onClose();
                  }}
                >
                  在大纲中编辑
                </button>
                <p className="text-[11px] text-slate-400">
                  {autoSaveStatus === "pending"
                    ? "保存中…"
                    : savedAt
                      ? `上次保存 ${savedAt.toLocaleTimeString("zh-CN")}`
                      : ""}
                </p>
              </>
            ) : (
              <p className="text-slate-500">请选择章节。</p>
            )}
          </div>
        )}

        {activeTab === "refs" && (
          <div className="space-y-3 text-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">已上传资料（RAG）</p>
            {refsLoading ? (
              <p className="text-slate-500">检索中…</p>
            ) : refHits.length === 0 ? (
              <p className="text-xs text-slate-500">暂无匹配片段。请先在书稿设定中上传并等待解析完成。</p>
            ) : (
              <ul className="space-y-3">
                {refHits.map((h, i) => (
                  <li key={i} className="rounded-lg border border-slate-100 bg-white/80 p-2 text-xs text-slate-700">
                    <p className="max-h-28 overflow-y-auto whitespace-pre-wrap leading-relaxed">{h.content}</p>
                    <p className="mt-1 text-[10px] text-slate-400">{h.filename}</p>
                    <button
                      type="button"
                      className="mt-2 text-xs font-medium text-violet-700 hover:underline"
                      onClick={() => {
                        onInsertReference?.(h.content, h.filename);
                        toast.success("已插入引用块");
                      }}
                    >
                      插入
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {activeTab === "literature" && (
          <LiteraturePanel
            bookId={bookId}
            citationStyle={citationStyle}
            defaultQuery={activeChapter?.title ?? ""}
            mode="editor"
            onInsertQuotes={(quotes) => onInsertLiteratureQuotes?.(quotes)}
          />
        )}

        {activeTab === "ai" && (
          <div className="flex min-h-[min(420px,65vh)] flex-col">
          <AiAssistantPanel
            bookId={bookId}
            chapterIndex={chapterIndex}
            aiModel={aiModel}
            llmCatalog={llmCatalog}
            llmCatalogLoading={llmCatalogLoading}
            onModelChange={onModelChange}
            selectionText={editorSelectionText}
            assistantSeed={assistantSeed}
            onConsumeAssistantSeed={onConsumeAssistantSeed}
            chapterContext={chapterContext}
            cursorParagraph={chapterContext.slice(0, 400)}
            quotedFigureId={quotedFigureId}
            quotedFigureAnnotation={quotedFigureAnnotation}
            onClearFigureQuote={onClearFigureQuote}
            onPreviewReady={(payload) => onAiPreviewReady?.(payload)}
            onFigureReady={onFigureReady}
          />
          </div>
        )}

        {activeTab === "review" && (
          <ReviewPanel
            bookId={bookId}
            chapterIndex={chapterIndex}
            chapterTitle={activeChapter?.title}
            selectionText={editorSelectionText}
            onApplySuggestion={onApplyReviewFix}
          />
        )}
      </div>
    </aside>
  );
}

export function AuxPanelFab({ onOpen }: { onOpen: () => void }) {
  return (
    <button
      type="button"
      className="editor-aux-panel-trigger"
      onClick={onOpen}
      title="打开辅助面板"
      aria-label="打开辅助面板"
    >
      <PenLine className="h-5 w-5" aria-hidden />
    </button>
  );
}
