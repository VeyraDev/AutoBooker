import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  listTurns,
  sendTurn,
  type ToolResult,
} from "@/features/assistant/api/assistantApi";
import {
  buildSeedFromToolResults,
  mergePanelSeed,
  panelHintToTab,
  type PanelToolSeed,
} from "@/features/assistant/toolDispatch";
import type { RightPanelTab } from "@/components/editor/RightPanel";

type Options = {
  bookId: string;
  chapterIndex?: number | null;
  onPanelTab?: (tab: RightPanelTab) => void;
  onPanelSeed?: (seed: PanelToolSeed | ((prev: PanelToolSeed) => PanelToolSeed)) => void;
  onOpenPanel?: () => void;
};

export function useGlobalAssistant({
  bookId,
  chapterIndex,
  onPanelTab,
  onPanelSeed,
  onOpenPanel,
}: Options) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [localTurns, setLocalTurns] = useState<Array<{ id: string; user_message: string; assistant_message: string; created_at: string }>>([]);
  const [pendingConfirmation, setPendingConfirmation] = useState<string | null>(null);

  const turnsQuery = useQuery({
    queryKey: ["assistantTurns", bookId],
    queryFn: () => listTurns(bookId),
    enabled: Boolean(bookId),
  });

  const sendMutation = useMutation({
    mutationFn: (message: string) => sendTurn(bookId, message, chapterIndex),
    onSuccess: async (data, message) => {
      setLocalTurns((prev) => [
        {
          id: data.turn_id,
          user_message: message,
          assistant_message: data.assistant_message,
          created_at: new Date().toISOString(),
        },
        ...prev,
      ]);
      await qc.invalidateQueries({ queryKey: ["assistantTurns", bookId] });
      if (data.memories?.length) {
        await qc.invalidateQueries({ queryKey: ["memories", bookId] });
      }

      const toolResults = (data.tool_results ?? []) as ToolResult[];
      if (toolResults.length) {
        const seed = buildSeedFromToolResults(toolResults);
        onPanelSeed?.(seed);
        onOpenPanel?.();
        const tab = toolResults.map((r) => panelHintToTab(r.panel_hint)).find(Boolean);
        if (tab) onPanelTab?.(tab);
        const workspace = toolResults.find((r) => r.panel_hint === "review_workspace" && r.ok);
        if (workspace) {
          const ch = (workspace.data.chapter_index as number | undefined) ?? chapterIndex;
          const qs = ch != null ? `?chapter=${ch}` : "";
          navigate(`/app/books/${bookId}/review${qs}`);
        }
      }

      const confirm = data.pending_confirmations?.[0];
      if (confirm) {
        setPendingConfirmation(String(confirm.data?.preview ?? confirm.name));
      }
    },
  });

  const dispatchToolResults = useCallback(
    (results: ToolResult[]) => {
      const seed = buildSeedFromToolResults(results);
      onPanelSeed?.((prev) => mergePanelSeed(prev ?? {}, seed));
      onOpenPanel?.();
      const tab = results.map((r) => panelHintToTab(r.panel_hint)).find(Boolean);
      if (tab) onPanelTab?.(tab);
    },
    [onOpenPanel, onPanelSeed, onPanelTab],
  );

  return {
    turns: localTurns.length ? localTurns : (turnsQuery.data ?? []),
    turnsLoading: turnsQuery.isLoading,
    sendMessage: async (message: string) => {
      const trimmed = message.trim();
      if (!trimmed) return;
      return sendMutation.mutateAsync(trimmed);
    },
    sending: sendMutation.isPending,
    lastResponse: sendMutation.data,
    pendingConfirmation,
    clearConfirmation: () => setPendingConfirmation(null),
    dispatchToolResults,
  };
}
