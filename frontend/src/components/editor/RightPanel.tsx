import { BookOpen, ClipboardList, MessageSquareText, PenLine, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

import { searchReferences } from "@/api/references";
import type { AutoSaveUi } from "@/components/editor/EditorTopBar";
import type { OutlineChapter } from "@/types/outline";

export type RightPanelTab = "detail" | "refs" | "ai" | "review";

const MODEL_OPTIONS = ["qwen-max", "qwen-turbo", "qwen-plus"];

type Props = {
  bookId: string;
  onClose: () => void;
  activeChapter: OutlineChapter | null;
  autoSaveStatus: AutoSaveUi;
  savedAt: Date | null;
  aiModel: string | null;
  onModelChange: (model: string) => void;
  /** 由 BubbleMenu「…」联动打开时切换到 AI 并预填选区 */
  activeTab: RightPanelTab;
  onTabChange: (t: RightPanelTab) => void;
  assistantSeed: string;
  onConsumeAssistantSeed: () => void;
  /** 参考资料插入到编辑器 */
  onInsertReference?: (plain: string, filename: string) => void;
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
  onModelChange,
  activeTab,
  onTabChange,
  assistantSeed,
  onConsumeAssistantSeed,
  onInsertReference,
  onOpenOutlineEditor,
}: Props) {
  const [aiInstruction, setAiInstruction] = useState("");
  const [refHits, setRefHits] = useState<{ content: string; filename: string }[]>([]);
  const [refsLoading, setRefsLoading] = useState(false);

  useEffect(() => {
    if (!assistantSeed.trim()) return;
    setAiInstruction((prev) => (prev.trim() ? `${prev.trim()}\n\n${assistantSeed.trim()}` : assistantSeed.trim()));
    onConsumeAssistantSeed();
  }, [assistantSeed, onConsumeAssistantSeed]);

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
        {tabBtn("refs", <BookOpen className="h-4 w-4" aria-hidden />, "参考资料")}
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
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">参考资料</p>
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

        {activeTab === "ai" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">模型</p>
              <select
                className="input h-8 max-w-[9rem] cursor-pointer py-1 text-xs"
                value={aiModel ?? MODEL_OPTIONS[0]}
                onChange={(e) => onModelChange(e.target.value)}
                aria-label="模型选择"
              >
                {MODEL_OPTIONS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">指令</p>
            <textarea
              className="input min-h-[120px] text-sm"
              placeholder="输入指令，例如：把最后一段改得更口语化…"
              value={aiInstruction}
              onChange={(e) => setAiInstruction(e.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary h-9 px-3 text-xs" onClick={() => toast("全文指令处理即将接入工作流")}>
                发送到编辑器
              </button>
            </div>
          </div>
        )}

        {activeTab === "review" && (
          <div className="space-y-4 text-sm">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">审校</p>
              <div className="mt-2 rounded-xl border border-dashed border-slate-200 bg-white/80 p-4 text-slate-600">
                <p className="font-medium text-ink">审校功能开发中</p>
                <p className="mt-2 text-xs text-slate-500">将在此展示 ReviewAgent 报告。</p>
              </div>
            </div>
            <hr className="border-slate-100" />
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">AI 降重</p>
              <div className="mt-2 rounded-xl border border-dashed border-slate-200 bg-white/80 p-4 text-slate-600">
                <p className="font-medium text-ink">降重功能开发中</p>
              </div>
            </div>
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
