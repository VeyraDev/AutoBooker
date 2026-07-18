import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";

import {
  listSources,
  listTurns,
  sendTurn,
  type AssistantTrace,
  type ConfirmationPreview,
  type ExtractedRequirement,
  type OutlineRoute,
  type SettingOrigin,
  type SourceItem,
  type ToolResult,
  type TurnListItem,
  type TurnResponse,
  type WritingBasis,
} from "@/features/assistant/api/assistantApi";
import { normalizeSearchPayload } from "@/features/assistant/components/LiteratureSearchCard";
import { useStreamingReveal } from "@/lib/useStreamingReveal";

export type PendingTurn = {
  userMessage: string;
  phase: "thinking" | "streaming";
  assistantMessage: string;
  turnId?: string;
  traces?: AssistantTrace[];
  searchResult?: Record<string, unknown> | null;
};

type Options = {
  /** 新建书稿的创作意图，在无历史对话时自动作为首轮输入 */
  initialMessage?: string | null;
};

function turnErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.code === "ECONNABORTED") return "助手响应超时，请稍后重试";
    const raw = error.response?.data;
    if (raw && typeof raw === "object" && "detail" in raw) {
      const detail = (raw as { detail: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) return detail;
    }
    if (error.response?.status === 502) return "模型服务暂时不可用，请稍后重试";
    if (!error.response) return "无法连接服务器，请确认后端已启动";
  }
  return error instanceof Error ? error.message : "发送失败";
}

export function useAssistantConversation(bookId: string, options?: Options) {
  const qc = useQueryClient();
  const initialSentRef = useRef(false);
  const [pendingTurn, setPendingTurn] = useState<PendingTurn | null>(null);
  const [lastTurnTraces, setLastTurnTraces] = useState<Record<string, AssistantTrace[]>>({});

  const turnsQuery = useQuery({
    queryKey: ["assistantTurns", bookId],
    queryFn: () => listTurns(bookId),
    enabled: Boolean(bookId),
  });

  const sourcesQuery = useQuery({
    queryKey: ["sources", bookId],
    queryFn: () => listSources(bookId),
    enabled: Boolean(bookId),
  });

  const [lastQuickFillOpId, setLastQuickFillOpId] = useState<string | null>(null);
  const [lastSettingOrigins, setLastSettingOrigins] = useState<Record<string, SettingOrigin>>({});
  const [lastConfirmedRequirements, setLastConfirmedRequirements] = useState<ExtractedRequirement[]>([]);
  const [lastOutlineRoute, setLastOutlineRoute] = useState<OutlineRoute | null>(null);
  const [externalSearch, setExternalSearch] = useState<Record<string, unknown> | null>(null);

  // Rehydrate literature panel from persisted turn search (survives refresh / HMR)
  useEffect(() => {
    const rows = turnsQuery.data ?? [];
    const hit = rows.find((t) => t.search_result);
    if (!hit?.search_result) return;
    const normalized = normalizeSearchPayload(hit.search_result);
    if (normalized) setExternalSearch(normalized);
  }, [turnsQuery.data]);

  const applyTurnSuccess = useCallback(
    async (data: TurnResponse) => {
      if (data.turn_id && data.traces?.length) {
        setLastTurnTraces((prev) => ({ ...prev, [data.turn_id]: data.traces ?? [] }));
      }
      if (data.quick_fill_operation_id) {
        setLastQuickFillOpId(data.quick_fill_operation_id);
      }
      if (data.setting_origins) {
        setLastSettingOrigins(data.setting_origins);
      }
      if (data.confirmed_requirements) {
        setLastConfirmedRequirements(data.confirmed_requirements);
      }
      if (data.outline_route) {
        setLastOutlineRoute(data.outline_route);
      }
      const fromSearch = data.search_result?.result;
      const fromTool =
        data.tool_results?.find(
          (r) =>
            (r.name === "search_person_works" || r.name === "search_references" || r.name === "search_literature") &&
            r.ok,
        )?.data;
      const nested =
        fromTool && typeof fromTool === "object" && "result" in fromTool
          ? (fromTool as { result?: unknown }).result
          : null;
      const next =
        (fromSearch && typeof fromSearch === "object" ? (fromSearch as Record<string, unknown>) : null) ??
        (nested && typeof nested === "object" ? (nested as Record<string, unknown>) : null) ??
        (fromTool && typeof fromTool === "object" ? (fromTool as Record<string, unknown>) : null);
      let searchPayload: Record<string, unknown> | null = null;
      if (data.search_result && typeof data.search_result === "object") {
        searchPayload = normalizeSearchPayload(data.search_result as Record<string, unknown>);
      } else if (next) {
        const meta =
          fromTool && typeof fromTool === "object" ? (fromTool as Record<string, unknown>) : {};
        searchPayload = normalizeSearchPayload({
          ...meta,
          result: next,
        });
      }
      if (searchPayload) setExternalSearch(searchPayload);
      setPendingTurn((prev) =>
        prev
          ? {
              ...prev,
              phase: "streaming",
              assistantMessage: data.assistant_message,
              turnId: data.turn_id,
              traces: data.traces,
              searchResult: searchPayload ?? prev.searchResult ?? null,
            }
          : null,
      );
      if (data.writing_basis) {
        qc.setQueryData(["writingBasis", bookId], data.writing_basis);
      }
      void qc.invalidateQueries({ queryKey: ["book", bookId] });
    },
    [bookId, qc],
  );

  const prependSource = useCallback(
    (item: SourceItem) => {
      qc.setQueryData<SourceItem[]>(["sources", bookId], (prev) => {
        const list = prev ?? [];
        if (list.some((s) => s.id === item.id)) return list;
        return [...list, item];
      });
    },
    [bookId, qc],
  );

  const removeSource = useCallback(
    (sourceId: string) => {
      qc.setQueryData<SourceItem[]>(["sources", bookId], (prev) => (prev ?? []).filter((s) => s.id !== sourceId));
    },
    [bookId, qc],
  );

  const refreshSources = useCallback(async () => {
    await qc.invalidateQueries({ queryKey: ["sources", bookId] });
  }, [bookId, qc]);

  const finalizePendingTurn = useCallback(async () => {
    setPendingTurn(null);
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["assistantTurns", bookId] }),
      qc.invalidateQueries({ queryKey: ["sources", bookId] }),
      qc.invalidateQueries({ queryKey: ["memories", bookId] }),
      qc.invalidateQueries({ queryKey: ["writingBasis", bookId] }),
      qc.invalidateQueries({ queryKey: ["book", bookId] }),
    ]);
  }, [bookId, qc]);

  const sendMutation = useMutation({
    mutationFn: (payload: { message: string; mode?: "normal" | "quick_fill" }) =>
      sendTurn(bookId, payload.message, null, payload.mode ?? "normal"),
    onMutate: (payload) => {
      setPendingTurn({
        userMessage: payload.mode === "quick_fill" ? "（快速补齐）" : payload.message,
        phase: "thinking",
        assistantMessage: "",
      });
    },
    onSuccess: async (data) => {
      await applyTurnSuccess(data);
    },
    onError: (err) => {
      setPendingTurn(null);
      toast.error(turnErrorMessage(err));
    },
  });

  const sendMessage = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text || sendMutation.isPending || pendingTurn) return;
      return sendMutation.mutateAsync({ message: text, mode: "normal" });
    },
    [pendingTurn, sendMutation],
  );

  const quickFill = useCallback(async () => {
    if (sendMutation.isPending || pendingTurn) return;
    return sendMutation.mutateAsync({ message: "", mode: "quick_fill" });
  }, [pendingTurn, sendMutation]);

  const stream = useStreamingReveal(pendingTurn?.assistantMessage ?? "", pendingTurn?.phase === "streaming");

  useEffect(() => {
    if (pendingTurn?.phase !== "streaming" || !stream.done) return;
    void finalizePendingTurn();
  }, [pendingTurn?.phase, stream.done, finalizePendingTurn]);

  useEffect(() => {
    const goal = options?.initialMessage?.trim();
    if (!goal || initialSentRef.current) return;
    if (turnsQuery.isLoading) return;
    if ((turnsQuery.data?.length ?? 0) > 0) return;
    if (pendingTurn || sendMutation.isPending) return;
    const bootKey = `assistant:bootstrapped:${bookId}`;
    if (typeof sessionStorage !== "undefined" && sessionStorage.getItem(bootKey)) {
      initialSentRef.current = true;
      return;
    }
    initialSentRef.current = true;
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.setItem(bootKey, "1");
    }
    void sendMessage(goal);
  }, [
    options?.initialMessage,
    turnsQuery.isLoading,
    turnsQuery.data,
    pendingTurn,
    sendMutation.isPending,
    sendMessage,
  ]);

  const lastResponse = sendMutation.data;

  return {
    turns: (turnsQuery.data ?? []) as TurnListItem[],
    turnsLoading: turnsQuery.isLoading,
    turnsError: turnsQuery.error,
    refetchTurns: turnsQuery.refetch,
    sources: (sourcesQuery.data ?? []) as SourceItem[],
    sourcesLoading: sourcesQuery.isLoading,
    sourcesError: sourcesQuery.error,
    refetchSources: sourcesQuery.refetch,
    refreshSources,
    prependSource,
    removeSource,
    sendMessage,
    quickFill,
    sending: sendMutation.isPending || pendingTurn?.phase === "thinking",
    streaming: pendingTurn?.phase === "streaming",
    streamingText: stream.visible,
    pendingTurn,
    sendError: sendMutation.error,
    lastBasis: lastResponse?.writing_basis as WritingBasis | undefined,
    openQuestions: lastResponse?.open_questions ?? [],
    toolResults: (lastResponse?.tool_results ?? []) as ToolResult[],
    pendingConfirmations: (lastResponse?.pending_confirmations ?? []) as ConfirmationPreview[],
    topicProposal: lastResponse?.tool_results?.find((r) => r.name === "propose_book_topics" && r.ok)?.data
      ?.proposal as Record<string, unknown> | undefined,
    externalSearch,
    turnTracesById: lastTurnTraces,
    lastQuickFillOpId,
    lastSettingOrigins,
    lastConfirmedRequirements,
    lastOutlineRoute,
  };
}
