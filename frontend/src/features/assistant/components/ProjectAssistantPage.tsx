import { ChevronLeft } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import { getBook } from "@/api/books";
import { generateOutline } from "@/api/outline";
import { getOutlineReadiness, sendTurn } from "@/features/assistant/api/assistantApi";
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
  const qc = useQueryClient();
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

  async function runOutlineGenerate(opts?: { confirmed_source_id?: string; force?: boolean }) {
    setProceeding(true);
    const toastId = toast.loading("正在完成启动并生成大纲…");
    try {
      await completeProjectStart(bookId);
      const book = await getBook(bookId);
      qc.setQueryData(["book", bookId], { ...book, status: "outline_generating" });
      void qc.invalidateQueries({ queryKey: ["books"] });
      const nextOutline = await generateOutline(bookId, {
        topic_override: null,
        target_audience: book.target_audience?.trim() || null,
        topic_brief: book.topic_brief?.trim() || null,
        confirmed_source_id: opts?.confirmed_source_id ?? null,
        force: opts?.force ?? false,
      });
      qc.setQueryData(["outline", bookId], nextOutline);
      const freshBook = await getBook(bookId);
      qc.setQueryData(["book", bookId], freshBook);
      toast.success("大纲已生成", { id: toastId });
      await intakeQuery.refetch();
      await onComplete?.();
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        const detail = err.response.data?.detail as
          | {
              code?: string;
              message?: string;
              candidate_source_ids?: string[];
              outline_route?: { source_id?: string; candidate_source_ids?: string[] };
            }
          | undefined;
        const candidates =
          detail?.candidate_source_ids ?? detail?.outline_route?.candidate_source_ids ?? [];
        if (candidates.length > 0) {
          const pick = window.prompt(
            `${detail?.message || "请确认主大纲来源"}\n候选 ID：\n${candidates.join("\n")}\n\n请输入要使用的 source_id（取消则中止）`,
            candidates[0],
          );
          if (pick?.trim()) {
            toast.dismiss(toastId);
            await runOutlineGenerate({ confirmed_source_id: pick.trim() });
            return;
          }
        }
      }
      toast.error("生成大纲失败，请补充设定或检查网络后重试", { id: toastId });
      try {
        const fresh = await getBook(bookId);
        qc.setQueryData(["book", bookId], fresh);
      } catch {
        /* ignore */
      }
    } finally {
      setProceeding(false);
    }
  }

  async function handleProceed() {
    try {
      const readiness = await getOutlineReadiness(bookId);
      if (readiness.missing.length > 0) {
        const ok = window.confirm(
          `当前书稿设定还缺少：${readiness.missing.join("、")}。设定不完整可能导致大纲偏离，是否仍然生成？\n\n确定=仍然生成，取消=返回完善`,
        );
        if (!ok) return;
      }
      const route = readiness.outline_route ?? conv.lastOutlineRoute;
      if (route?.needs_confirmation && (route.candidate_source_ids?.length ?? 0) > 0) {
        const pick = window.prompt(
          `助手判断需要确认主大纲来源。\n${route.reason || ""}\n候选：\n${(route.candidate_source_ids || []).join("\n")}\n\n请输入 source_id`,
          route.source_id || route.candidate_source_ids?.[0] || "",
        );
        if (!pick?.trim()) return;
        await runOutlineGenerate({ confirmed_source_id: pick.trim() });
        return;
      }
      await runOutlineGenerate({
        confirmed_source_id: route?.source_id || undefined,
      });
    } catch {
      toast.error("无法检查设定完整性，请稍后重试");
    }
  }

  async function handleApplyTopic(index: number) {
    const topic = topics[index];
    if (!topic?.title) return;
    setApplyingTopic(true);
    try {
      await sendTurn(bookId, `请将选题「${topic.title}」整理进主题要点与书名建议`);
      toast.success("已请助手写入正式设定");
      void bookQuery.refetch();
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
            className="icon-button h-9 shrink-0 px-2 text-sm text-slate-600 disabled:opacity-50"
            title={proceeding ? "大纲生成中，完成后可返回" : "返回书架"}
            aria-label="返回书架"
            disabled={proceeding}
            onClick={() => onExit?.()}
          >
            <ChevronLeft className="h-5 w-5" />
            <span className="hidden sm:inline">返回书架</span>
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-sm font-semibold text-slate-800">{book?.title ?? "书稿"}</h1>
            <p className="text-xs text-slate-500">书稿设定助手 · 可随时退出，进度会自动保存</p>
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
            onQuickFill={conv.quickFill}
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
              book={book}
              intake={intakeQuery.data?.intake}
              loading={intakeQuery.isLoading || bookQuery.isLoading}
              proceeding={proceeding}
              settingOrigins={conv.lastSettingOrigins}
              confirmedRequirements={conv.lastConfirmedRequirements}
              quickFillOpId={conv.lastQuickFillOpId}
              onProceed={() => void handleProceed()}
              onOpenAdvanced={() => setAdvancedOpen(true)}
              onBookUpdated={(b) => {
                qc.setQueryData(["book", bookId], b);
                void bookQuery.refetch();
              }}
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
