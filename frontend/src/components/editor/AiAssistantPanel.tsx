import axios from "axios";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

import { callAssistant } from "@/api/assistant";
import AssistantFeaturePanel, { type FeatureSelection } from "@/components/editor/AssistantFeaturePanel";
import type { EditorAiPreviewPayload } from "@/types/aiPreview";

const TEXT_INTENTS = new Set([
  "polish",
  "rewrite",
  "expand",
  "condense",
  "style_adjust",
  "term_check",
]);

type Props = {
  bookId: string;
  chapterIndex: number | null;
  selectionText: string;
  assistantSeed: string;
  onConsumeAssistantSeed: () => void;
  chapterContext: string;
  cursorParagraph?: string;
  quotedFigureId?: string | null;
  quotedFigureAnnotation?: string;
  onClearFigureQuote?: () => void;
  onPreviewReady: (payload: EditorAiPreviewPayload) => void;
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
};

export default function AiAssistantPanel({
  bookId,
  chapterIndex,
  selectionText,
  assistantSeed,
  onConsumeAssistantSeed,
  chapterContext,
  cursorParagraph = "",
  quotedFigureId = null,
  quotedFigureAnnotation = "",
  onClearFigureQuote,
  onPreviewReady,
  onFigureReady,
}: Props) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [pinnedSelection, setPinnedSelection] = useState("");
  const [activeFeature, setActiveFeature] = useState<FeatureSelection | null>(null);
  const [chartMenuOpen, setChartMenuOpen] = useState(false);

  useEffect(() => {
    if (selectionText.trim()) setPinnedSelection(selectionText.trim());
  }, [selectionText]);

  useEffect(() => {
    if (assistantSeed.trim()) {
      setPinnedSelection(assistantSeed.trim());
      onConsumeAssistantSeed();
    }
  }, [assistantSeed, onConsumeAssistantSeed]);

  const displaySelection = pinnedSelection || selectionText.trim();
  const isTextFeature = activeFeature ? TEXT_INTENTS.has(activeFeature.intent) : false;
  const isImageFeature = activeFeature ? !TEXT_INTENTS.has(activeFeature.intent) : false;

  async function handleSend() {
    if (chapterIndex == null) {
      toast.error("请先选择章节");
      return;
    }

    const intent = activeFeature?.intent;
    const needsSelection = isTextFeature;
    if (needsSelection && !displaySelection) {
      toast.error("请先在正文选中要处理的段落");
      return;
    }
    if (!intent && !message.trim()) {
      toast.error("请选择功能或输入指令");
      return;
    }

    setBusy(true);
    try {
      const body = {
        user_text: message.trim(),
        selected_text: displaySelection || undefined,
        figure_id: quotedFigureId ?? undefined,
        cursor_paragraph: cursorParagraph || chapterContext.slice(0, 400) || undefined,
        explicit_intent:
          quotedFigureId && isImageFeature
            ? "regen_figure"
            : quotedFigureId && !intent && message.trim()
              ? "regen_figure"
              : intent,
        chart_type: activeFeature?.chart_type,
        sub_kind: activeFeature?.sub_kind,
      };

      const res = await callAssistant(bookId, chapterIndex, body);

      if (res.type === "confirm") {
        toast(res.message || "请从功能面板选择具体操作，或说得更具体一些");
        return;
      }

      if (res.type === "figure") {
        onFigureReady?.({
          figure_id: res.figure_id,
          file_url: res.file_url,
          figure_number: res.figure_number,
          status: res.status,
          caption: res.caption,
          figure_type: res.figure_type,
          replace_only: Boolean(quotedFigureId),
          target_figure_id: quotedFigureId ?? res.figure_id,
        });
        toast.success(quotedFigureId ? "新图已生成，请查看正文中的图表" : "图表已生成");
      } else {
        const quote = displaySelection || cursorParagraph.slice(0, 200) || "选中内容";
        onPreviewReady({
          quote,
          suggestion: res.content,
          kind: isTextFeature ? "replace" : "insert",
        });
        toast.success("已在正文原位置显示预览");
      }
    } catch (e) {
      const detail =
        axios.isAxiosError(e) && typeof e.response?.data?.detail === "string"
          ? e.response.data.detail
          : e instanceof Error
            ? e.message
            : "AI 处理失败";
      toast.error(detail.length > 160 ? `${detail.slice(0, 160)}…` : detail);
    } finally {
      setBusy(false);
    }
  }

  const placeholder =
    activeFeature?.placeholder ??
    (displaySelection ? "输入补充说明…" : "选择下方功能，或输入写作要求");

  return (
    <div className="ai-assistant-panel flex min-h-0 flex-1 flex-col gap-3">
      {displaySelection ? (
        <div className="rounded-lg border border-slate-200 bg-slate-100/90 px-3 py-2.5">
          <div className="flex items-start justify-between gap-2">
            <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">已选正文</p>
            <button
              type="button"
              className="shrink-0 text-slate-400 hover:text-slate-700"
              aria-label="清除选区"
              onClick={() => setPinnedSelection("")}
            >
              ×
            </button>
          </div>
          <p className="mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-slate-700">
            {displaySelection}
          </p>
        </div>
      ) : quotedFigureId ? (
        <div className="rounded-lg border border-violet-200 bg-violet-50/80 px-3 py-2.5">
          <div className="flex items-start justify-between gap-2">
            <p className="text-[10px] font-medium uppercase tracking-wide text-violet-700">已引用图表</p>
            <button type="button" className="text-violet-500 hover:text-violet-800" onClick={onClearFigureQuote}>
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <p className="mt-1 text-xs text-violet-900">{quotedFigureAnnotation || "当前图表"}</p>
        </div>
      ) : (
        <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
          选中正文或点击图表「引用」后，内容将显示在此处
        </p>
      )}

      <div className="ai-assistant-composer flex min-h-0 flex-1 flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
        <textarea
          className="min-h-[72px] flex-1 resize-none border-0 bg-transparent px-3 pt-3 text-sm outline-none ring-0 placeholder:text-slate-400"
          placeholder={placeholder}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!busy) void handleSend();
            }
          }}
        />
        {activeFeature ? (
          <div className="border-t border-slate-100 px-2 py-1.5">
            <span className="inline-flex items-center gap-1 rounded-md bg-violet-100 px-2 py-1 text-xs font-medium text-violet-900">
              {activeFeature.label}
              <button
                type="button"
                className="rounded p-0.5 text-violet-600 hover:bg-violet-200/60"
                aria-label="取消功能"
                onClick={() => setActiveFeature(null)}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          </div>
        ) : null}
        <AssistantFeaturePanel
          active={activeFeature}
          onSelect={setActiveFeature}
          chartMenuOpen={chartMenuOpen}
          onChartMenuOpen={setChartMenuOpen}
        />
      </div>

      <button
        type="button"
        className="btn-primary h-9 w-full shrink-0 text-xs disabled:opacity-50"
        disabled={busy || chapterIndex == null}
        onClick={() => void handleSend()}
      >
        {busy ? "处理中…" : isImageFeature ? "生成图像" : "发送"}
      </button>
    </div>
  );
}
