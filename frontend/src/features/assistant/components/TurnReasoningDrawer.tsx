import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import AssistantMarkdown from "@/features/assistant/components/AssistantMarkdown";
import { listTraces, type AssistantTrace } from "@/features/assistant/api/assistantApi";

type Props = {
  bookId: string;
  turnId: string;
  /** 本轮刚完成时可内联传入，避免额外请求 */
  inlineTraces?: AssistantTrace[];
};

function isUserEchoEvidence(text: string): boolean {
  const s = text.trim();
  if (!s) return true;
  return /^(用户原话|用户说|用户提到|用户表示|用户输入|用户本轮|用户消息)[:：]?/i.test(s);
}

function traceBody(trace: AssistantTrace): string {
  const parts: string[] = [];
  const claim = trace.claim?.trim();
  if (claim) parts.push(claim);
  const reason = trace.reason_summary?.trim();
  if (reason) parts.push(reason);
  const evidence = (trace.evidence ?? [])
    .map((e) => String(e).trim())
    .filter((e) => e && !isUserEchoEvidence(e));
  if (evidence.length) {
    parts.push(evidence.map((e) => `- ${e}`).join("\n"));
  }
  return parts.join("\n\n");
}

export default function TurnReasoningDrawer({ bookId, turnId, inlineTraces }: Props) {
  const [open, setOpen] = useState(false);
  const tracesQuery = useQuery({
    queryKey: ["assistantTraces", bookId, turnId],
    queryFn: () => listTraces(bookId, turnId),
    enabled: open && !inlineTraces?.length,
    staleTime: 60_000,
  });

  const traces = inlineTraces?.length ? inlineTraces : tracesQuery.data ?? [];
  const loading = open && !inlineTraces?.length && tracesQuery.isLoading;
  const traceItems = useMemo(
    () =>
      traces
        .map((t) => ({ id: t.id, body: traceBody(t) }))
        .filter((item) => item.body.trim()),
    [traces],
  );

  return (
    <div className="mb-2">
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        思考过程
        {inlineTraces?.length ? <span className="text-slate-400">（{inlineTraces.length}）</span> : null}
      </button>
      {open ? (
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-2">
          {loading ? (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              加载思考链…
            </div>
          ) : !traceItems.length ? (
            <p className="text-xs text-slate-500">本轮未记录可展开的思考链。</p>
          ) : (
            <ul className="space-y-3">
              {traceItems.map((item) => (
                <li key={item.id} className="rounded border border-slate-200 bg-white p-2">
                  <AssistantMarkdown content={item.body} className="text-xs" />
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
