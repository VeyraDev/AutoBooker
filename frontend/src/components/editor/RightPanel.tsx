import { ClipboardList, GraduationCap, ImageIcon, MessageSquareText, PenLine, X } from "lucide-react";

import AiAssistantPanel from "@/components/editor/AiAssistantPanel";
import type { EditorAiPreviewPayload } from "@/types/aiPreview";
import FigureQuickPanel from "@/components/editor/FigureQuickPanel";
import LiteraturePanel from "@/components/editor/LiteraturePanel";
import type { AutoSaveUi } from "@/components/editor/EditorTopBar";
import type { CitationStyle } from "@/types/book";
import type { OutlineChapter } from "@/types/outline";

export type RightPanelTab = "detail" | "refs" | "literature" | "ai";

type Props = {
  bookId: string;
  onClose: () => void;
  activeChapter: OutlineChapter | null;
  autoSaveStatus: AutoSaveUi;
  savedAt: Date | null;
  /** 由 BubbleMenu「…」联动打开时切换到 AI 并预填选区 */
  activeTab: RightPanelTab;
  onTabChange: (t: RightPanelTab) => void;
  assistantSeed: string;
  onConsumeAssistantSeed: () => void;
  citationStyle?: CitationStyle | null;
  /** 参考资料插入到编辑器 */
  onInsertReference?: (plain: string, filename: string) => void;
  /** 文献叙述句预览插入（光标处） */
  onPreviewCitationInsert?: (payload: { sentence: string; node: Record<string, unknown> }) => void;
  onJumpToCitation?: (chapterIndex: number, nodeId: string) => void;
  onCitationDeleted?: (chapterIndex: number) => void;
  chapterIndex?: number | null;
  editorSelectionText?: string;
  chapterContext?: string;
  onAiPreviewReady?: (payload: EditorAiPreviewPayload) => boolean | void;
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
    replace_only?: boolean;
    target_figure_id?: string;
  }) => void;
  /** 打开全局大纲以编辑章节元信息 */
  onOpenOutlineEditor?: () => void;
  onFiguresChanged?: () => void;
  onFigureGenerated?: (fig: import("@/api/figures").FigureOut) => void;
  figureTableOverview?: import("@/api/figures").FigureTableOverviewItem[];
  getChapterTiptapJson?: () => Record<string, unknown> | null;
  onApplyChapterContent?: (payload: {
    tiptap_json: Record<string, unknown>;
    text: string;
    overview?: import("@/api/figures").FigureTableOverviewItem[];
  }) => void;
};

export default function RightPanel({
  bookId,
  onClose,
  activeChapter,
  autoSaveStatus,
  savedAt,
  activeTab,
  onTabChange,
  assistantSeed,
  onConsumeAssistantSeed,
  citationStyle = null,
  onInsertReference: _onInsertReference,
  onPreviewCitationInsert,
  onJumpToCitation,
  onCitationDeleted,
  chapterIndex = null,
  editorSelectionText = "",
  chapterContext = "",
  onAiPreviewReady,
  quotedFigureId = null,
  quotedFigureAnnotation = "",
  onClearFigureQuote,
  onFigureReady,
  onOpenOutlineEditor,
  onFiguresChanged,
  onFigureGenerated,
  figureTableOverview = [],
  getChapterTiptapJson,
  onApplyChapterContent,
}: Props) {
  void _onInsertReference;
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
        {tabBtn("refs", <ImageIcon className="h-4 w-4" aria-hidden />, "图表速览")}
        {tabBtn("literature", <GraduationCap className="h-4 w-4" aria-hidden />, "资料搜索")}
        {tabBtn("ai", <MessageSquareText className="h-4 w-4" aria-hidden />, "AI 助手")}
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
          <FigureQuickPanel
            bookId={bookId}
            chapterIndex={chapterIndex ?? null}
            initialOverview={figureTableOverview}
            onFiguresChanged={onFiguresChanged}
            onFigureGenerated={onFigureGenerated}
            getChapterTiptapJson={getChapterTiptapJson}
            onApplyChapterContent={onApplyChapterContent}
          />
        )}

        <div className={activeTab === "literature" ? "" : "hidden"}>
          <LiteraturePanel
            bookId={bookId}
            citationStyle={citationStyle}
            chapterIndex={chapterIndex ?? undefined}
            mode="editor"
            chapterContext={chapterContext}
            onPreviewInsert={onPreviewCitationInsert}
            onJumpToCitation={onJumpToCitation}
            onCitationDeleted={onCitationDeleted}
          />
        </div>

        {activeTab === "ai" && (
          <div className="flex min-h-[min(420px,65vh)] flex-col">
          <AiAssistantPanel
            bookId={bookId}
            chapterIndex={chapterIndex}
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
