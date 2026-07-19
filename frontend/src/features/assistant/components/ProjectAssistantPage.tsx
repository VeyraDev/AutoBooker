import { ChevronLeft } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";
import { useQuery } from "@tanstack/react-query";

import { getBook } from "@/api/books";
import { sendTurn } from "@/features/assistant/api/assistantApi";
import AdvancedSettingsDrawer from "@/features/assistant/components/AdvancedSettingsDrawer";
import ConversationPanel from "@/features/assistant/components/ConversationPanel";
import ProjectBriefPanel from "@/features/assistant/components/ProjectBriefPanel";
import SourceLibraryPanel from "@/features/assistant/components/SourceLibraryPanel";
import { useAssistantConversation } from "@/features/assistant/hooks/useAssistantConversation";
import { completeProjectStart, useIntake } from "@/features/intake/api/intakeApi";

type TopicItem = {
  title?: string;
  rationale?: string;
  audience?: string;
  feasibility?: string;
};

type Props = {
  bookId: string;
  onComplete?: () => void | Promise<void>;
  onExit?: () => void;
};

export default function ProjectAssistantPage({ bookId, onComplete, onExit }: Props) {
  const intakeQuery = useIntake(bookId);
  const initialMessage = intakeQuery.data?.intake?.raw_goal_text ?? null;
  const conv = useAssistantConversation(bookId, { initialMessage });
  const bookQuery = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
  });
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [proceeding, setProceeding] = useState(false);
  const [applyingTopic, setApplyingTopic] = useState(false);

  const topicProposal = conv.topicProposal as
    | { topics?: TopicItem[]; recommended_index?: number; source_disclaimer?: string }
    | undefined;
  const topics = topicProposal?.topics ?? [];

  async function handleProceed() {
    setProceeding(true);
    try {
      await completeProjectStart(bookId);
      await intakeQuery.refetch();
      toast.success("可以开始规划大纲了");
      await onComplete?.();
    } catch {
      toast.error("进入大纲失败，请补充创作意图或检查网络");
    } finally {
      setProceeding(false);
    }
  }

  async function handleApplyTopic(index: number) {
    const topic = topics[index];
    if (!topic?.title) return;
    setApplyingTopic(true);
    try {
      await sendTurn(
        bookId,
        `请确认采用选题「${topic.title}」并写入写作依据`,
      );
      toast.success("已写入写作依据");
    } catch {
      toast.error("写入选题失败");
    } finally {
      setApplyingTopic(false);
    }
  }

  const book = bookQuery.data;

  return (
    <>
      <div className="mx-auto flex w-full max-w-7xl flex-col">
        <header className="mb-3 flex items-center gap-3 px-1">
          <button
            type="button"
            className="icon-button h-9 shrink-0 px-2 text-sm text-slate-600"
            title="返回书架"
            aria-label="返回书架"
            onClick={() => onExit?.()}
          >
            <ChevronLeft className="h-5 w-5" />
            <span className="hidden sm:inline">返回书架</span>
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-sm font-semibold text-slate-800">{book?.title ?? "书稿"}</h1>
            <p className="text-xs text-slate-500">项目启动助手 · 可随时退出，进度会自动保存</p>
          </div>
        </header>
        {((conv.pendingConfirmations?.length ?? 0) > 0) ? (
          <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-medium">选题预览（需确认）</p>
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs">
              {String(conv.pendingConfirmations[0]?.data?.preview ?? "")}
            </pre>
          </div>
        ) : null}
        {topics.length > 0 ? (
          <div className="mb-3 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm">
            <p className="font-medium text-violet-900">推荐选题</p>
            <ul className="mt-2 space-y-2">
              {topics.map((t, i) => (
                <li key={t.title ?? i} className="rounded border border-violet-100 bg-white p-2 text-xs">
                  <p className="font-medium text-slate-800">
                    {i + 1}. {t.title}
                    {i === (topicProposal?.recommended_index ?? 0) ? "（推荐）" : ""}
                  </p>
                  {t.rationale ? <p className="mt-1 text-slate-600">{t.rationale}</p> : null}
                  <button
                    type="button"
                    className="mt-2 rounded bg-violet-600 px-2 py-1 text-[11px] text-white disabled:opacity-50"
                    disabled={applyingTopic}
                    onClick={() => void handleApplyTopic(i)}
                  >
                    采用此主题
                  </button>
                </li>
              ))}
            </ul>
            {topicProposal?.source_disclaimer ? (
              <p className="mt-2 text-[11px] text-violet-800">{topicProposal.source_disclaimer}</p>
            ) : null}
          </div>
        ) : null}
        <div className="flex h-[calc(100vh-4rem-3rem)] w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
          <ConversationPanel
            bookId={bookId}
            turns={conv.turns}
            loading={conv.turnsLoading}
            sending={conv.sending}
            streaming={conv.streaming}
            streamingText={conv.streamingText}
            pendingTurn={conv.pendingTurn}
            error={conv.sendError}
            turnTracesById={conv.turnTracesById}
            onSend={conv.sendMessage}
          />
          <div className="flex w-72 shrink-0 flex-col border-l border-slate-200 bg-white">
            <SourceLibraryPanel
              bookId={bookId}
              sources={conv.sources}
              loading={conv.sourcesLoading}
              error={conv.sourcesError}
              externalSearch={conv.externalSearch as Record<string, unknown> | null}
              onRefresh={() => conv.refreshSources()}
              onSourceUploaded={conv.prependSource}
              onSourceRemoved={conv.removeSource}
            />
          </div>
          <div className="flex w-80 shrink-0 flex-col border-l border-slate-200 bg-white">
            <ProjectBriefPanel
              intake={intakeQuery.data?.intake}
              bookTitle={book?.title ?? "书稿"}
              loading={intakeQuery.isLoading}
              proceeding={proceeding}
              onProceed={() => void handleProceed()}
              onOpenAdvanced={() => setAdvancedOpen(true)}
            />
          </div>
        </div>
      </div>
      {book ? (
        <AdvancedSettingsDrawer open={advancedOpen} book={book} onClose={() => setAdvancedOpen(false)} />
      ) : null}
    </>
  );
}
