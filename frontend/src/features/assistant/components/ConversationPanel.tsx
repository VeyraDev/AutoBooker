import axios from "axios";
import { Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import AssistantMarkdown from "@/features/assistant/components/AssistantMarkdown";
import TurnReasoningDrawer from "@/features/assistant/components/TurnReasoningDrawer";
import type { AssistantTrace, TurnListItem } from "@/features/assistant/api/assistantApi";
import type { PendingTurn } from "@/features/assistant/hooks/useAssistantConversation";

type Props = {
  bookId: string;
  turns: TurnListItem[];
  loading?: boolean;
  sending?: boolean;
  streaming?: boolean;
  streamingText?: string;
  pendingTurn?: PendingTurn | null;
  error?: unknown;
  turnTracesById?: Record<string, AssistantTrace[]>;
  onSend: (message: string) => Promise<unknown>;
  onQuickFill?: () => Promise<unknown>;
};

function sendErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.code === "ECONNABORTED") {
      return "请求超时：助手思考时间较长，请稍后重试。";
    }
    const raw = error.response?.data;
    if (raw && typeof raw === "object" && "detail" in raw) {
      const detail = (raw as { detail: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) return detail;
    }
    if (error.response?.status === 502) {
      return "模型服务暂时不可用，请稍后重试。";
    }
    if (!error.response) {
      return "无法连接服务器，请确认后端已启动后重试。";
    }
  }
  return error instanceof Error && error.message ? error.message : "发送失败，请重试。";
}

export default function ConversationPanel({
  bookId,
  turns,
  loading,
  sending,
  streaming,
  streamingText,
  pendingTurn,
  error,
  turnTracesById = {},
  onSend,
  onQuickFill,
}: Props) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const chronological = useMemo(() => [...turns].reverse(), [turns]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [chronological.length, sending, streaming, streamingText]);

  async function submit() {
    const text = input.trim();
    if (!text || sending || streaming) return;
    setInput("");
    await onSend(text);
  }

  const busy = sending || streaming;

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-base font-semibold text-slate-900">项目启动助手</h2>
        <p className="text-xs text-slate-500">自由描述你想写的书，或上传资料让助手先读一读。</p>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3">
        {loading ? <div className="text-sm text-slate-500">加载对话…</div> : null}
        {!loading && !chronological.length && !pendingTurn ? (
          <div className="rounded border border-dashed border-slate-200 p-4 text-sm text-slate-500">
            例如：我想写一本 AI 数字营销实战书，面向中小商家，不要写成趋势报告。
          </div>
        ) : null}
        {chronological.map((turn) => (
          <div key={turn.id} className="space-y-2">
            <div className="ml-auto max-w-[85%] rounded-lg bg-indigo-50 px-3 py-2 text-sm text-slate-800 whitespace-pre-wrap">
              {turn.user_message}
            </div>
            <div className="max-w-[90%] rounded-lg bg-white px-3 py-2 text-slate-700 shadow-sm ring-1 ring-slate-100">
              <TurnReasoningDrawer
                bookId={bookId}
                turnId={turn.id}
                inlineTraces={turnTracesById[turn.id]}
              />
              <AssistantMarkdown content={turn.assistant_message} />
            </div>
          </div>
        ))}
        {pendingTurn ? (
          <div className="space-y-2">
            <div className="ml-auto max-w-[85%] rounded-lg bg-indigo-50 px-3 py-2 text-sm text-slate-800 whitespace-pre-wrap">
              {pendingTurn.userMessage}
            </div>
            <div className="max-w-[90%] rounded-lg bg-white px-3 py-2 shadow-sm ring-1 ring-slate-100">
              {pendingTurn.phase === "thinking" ? (
                <div className="flex items-center gap-2 py-2 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />
                  助手思考中…
                </div>
              ) : (
                <>
                  {pendingTurn.traces?.length ? (
                    <TurnReasoningDrawer
                      bookId={bookId}
                      turnId={pendingTurn.turnId ?? "pending"}
                      inlineTraces={pendingTurn.traces}
                    />
                  ) : null}
                  <AssistantMarkdown content={streamingText ?? ""} />
                  {!streaming ? null : (
                    <span className="inline-block h-4 w-0.5 animate-pulse bg-indigo-400 align-middle" aria-hidden />
                  )}
                </>
              )}
            </div>
          </div>
        ) : null}
        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {sendErrorMessage(error)}
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>
      <div className="border-t border-slate-200 p-3">
        <div className="flex items-end gap-2">
          {onQuickFill ? (
            <button
              type="button"
              className="shrink-0 rounded border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              disabled={busy}
              title="根据当前对话与资料集中判断正式设定"
              onClick={() => void onQuickFill()}
            >
              快速补齐
            </button>
          ) : null}
          <textarea
            className="min-h-[44px] flex-1 rounded border border-slate-200 p-2 text-sm"
            rows={2}
            placeholder="输入你的想法、要求或问题…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={busy}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void submit();
              }
            }}
          />
          <button
            type="button"
            className="rounded bg-brand px-4 py-2 text-sm text-white disabled:opacity-50"
            disabled={busy || !input.trim()}
            onClick={() => void submit()}
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
