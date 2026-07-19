import { ChevronDown, ChevronUp, Loader2, MessageSquare, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useGlobalAssistant } from "@/features/assistant/hooks/useGlobalAssistant";
import type { PanelToolSeed } from "@/features/assistant/toolDispatch";
import type { RightPanelTab } from "@/components/editor/RightPanel";

type Props = {
  bookId: string;
  chapterIndex?: number | null;
  onPanelTab: (tab: RightPanelTab) => void;
  onPanelSeed: (seed: PanelToolSeed | ((prev: PanelToolSeed) => PanelToolSeed)) => void;
  onOpenPanel: () => void;
};

export default function GlobalAssistantDock({
  bookId,
  chapterIndex,
  onPanelTab,
  onPanelSeed,
  onOpenPanel,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const { turns, turnsLoading, sendMessage, sending, lastResponse, pendingConfirmation, clearConfirmation } =
    useGlobalAssistant({
      bookId,
      chapterIndex,
      onPanelTab,
      onPanelSeed,
      onOpenPanel,
    });

  useEffect(() => {
    if (expanded && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [turns, lastResponse, expanded]);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || sending) return;
    setInput("");
    setExpanded(true);
    try {
      await sendMessage(msg);
    } catch {
      /* toast handled by caller if needed */
    }
  };

  return (
    <div className="global-assistant-dock fixed bottom-4 left-1/2 z-40 w-[min(640px,calc(100vw-2rem))] -translate-x-1/2">
      {pendingConfirmation ? (
        <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 shadow">
          <p className="mb-1 font-medium">需您确认后再执行</p>
          <pre className="max-h-32 overflow-auto whitespace-pre-wrap text-xs">{pendingConfirmation}</pre>
          <button type="button" className="mt-2 text-xs text-amber-800 underline" onClick={clearConfirmation}>
            知道了
          </button>
        </div>
      ) : null}
      {expanded ? (
        <div className="mb-2 max-h-64 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-medium text-slate-700">策划助手</span>
            <button type="button" className="text-slate-500" onClick={() => setExpanded(false)} aria-label="收起">
              <ChevronDown className="h-4 w-4" />
            </button>
          </div>
          <div ref={listRef} className="max-h-48 space-y-2 overflow-y-auto p-3 text-sm">
            {turnsLoading ? (
              <p className="text-slate-400">加载对话…</p>
            ) : (
              [...turns].reverse().map((t) => (
                <div key={t.id} className="space-y-1">
                  {t.user_message ? (
                    <p className="rounded bg-violet-50 px-2 py-1 text-slate-800">{t.user_message}</p>
                  ) : null}
                  {t.assistant_message ? (
                    <p className="rounded bg-slate-50 px-2 py-1 text-slate-700">{t.assistant_message}</p>
                  ) : null}
                </div>
              ))
            )}
            {lastResponse?.assistant_message && !turns.find((t) => t.assistant_message === lastResponse.assistant_message) ? (
              <p className="rounded bg-slate-50 px-2 py-1 text-slate-700">{lastResponse.assistant_message}</p>
            ) : null}
          </div>
        </div>
      ) : null}
      <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 shadow-lg">
        <MessageSquare className="h-4 w-4 shrink-0 text-violet-600" />
        <input
          className="min-w-0 flex-1 bg-transparent text-sm outline-none"
          placeholder={chapterIndex != null ? `向助手提问（当前第 ${chapterIndex} 章）…` : "向策划助手提问…"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSend();
            }
          }}
        />
        <button
          type="button"
          className="rounded-full bg-violet-600 p-2 text-white disabled:opacity-50"
          disabled={sending || !input.trim()}
          onClick={() => void handleSend()}
          aria-label="发送"
        >
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
        <button
          type="button"
          className="text-slate-500"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? "收起对话" : "展开对话"}
        >
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}
