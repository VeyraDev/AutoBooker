import { X } from "lucide-react";
import toast from "react-hot-toast";

import type { EditorTool } from "@/components/editor/EditorSideTools";
import type { OutlineChapter } from "@/types/outline";
import type { AutoSaveUi } from "@/components/editor/EditorTopBar";

type Props = {
  tool: EditorTool;
  onClose: () => void;
  activeChapter: OutlineChapter | null;
  autoSaveStatus: AutoSaveUi;
  savedAt: Date | null;
};

export default function RightPanel({
  tool,
  onClose,
  activeChapter,
  autoSaveStatus,
  savedAt,
}: Props) {
  return (
    <aside className="right-panel" aria-label="AI 与辅助面板">
      <div className="right-panel-header">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-400">辅助面板</span>
        <button
          type="button"
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          onClick={onClose}
          title="关闭"
          aria-label="关闭辅助面板"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>

      <div className="right-panel-inner">
        {tool === "edit" && (
          <div className="space-y-3 text-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">当前章节</p>
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
                <p className="text-[11px] text-slate-400">
                  {autoSaveStatus === "pending"
                    ? "保存中…"
                    : savedAt
                      ? `上次保存 ${savedAt.toLocaleTimeString("zh-CN")}`
                      : ""}
                </p>
              </>
            ) : (
              <p className="text-slate-500">选择左侧章节或「书稿设定」查看详情。</p>
            )}
          </div>
        )}

        {tool === "ai" && (
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">AI 助手</p>
            <textarea
              className="input min-h-[100px] text-sm"
              placeholder="输入指令，例如：把最后一段改得更口语化…"
              disabled
            />
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary h-9 px-3 text-xs" onClick={() => toast("段落级重写未实现")}>
                重写此段
              </button>
              <button type="button" className="btn-secondary h-9 px-3 text-xs" onClick={() => toast("扩写未实现")}>
                扩写
              </button>
              <button type="button" className="btn-secondary h-9 px-3 text-xs" onClick={() => toast("缩写未实现")}>
                缩写
              </button>
            </div>
          </div>
        )}

        {tool === "review" && (
          <div className="rounded-xl border border-dashed border-slate-200 bg-white/80 p-4 text-sm text-slate-600">
            <p className="font-medium text-ink">审校功能开发中</p>
            <p className="mt-2 text-xs text-slate-500">将在此展示 ReviewAgent 报告（按严重程度排序）。</p>
          </div>
        )}

        {tool === "rewrite" && (
          <div className="rounded-xl border border-dashed border-slate-200 bg-white/80 p-4 text-sm text-slate-600">
            <p className="font-medium text-ink">降重功能开发中</p>
            <p className="mt-2 text-xs text-slate-500">可选择段落 / 章节 / 全书粒度并查看进度。</p>
          </div>
        )}
      </div>
    </aside>
  );
}
