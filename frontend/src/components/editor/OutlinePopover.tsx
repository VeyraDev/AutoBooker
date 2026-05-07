import { X } from "lucide-react";
import { useEffect } from "react";

import OutlineNavBody, { type OutlineNavBodyProps, type OutlineSelection } from "@/components/editor/OutlineNavBody";

type Props = OutlineNavBodyProps & {
  open: boolean;
  onClose: () => void;
  onSelect: (s: OutlineSelection) => void;
};

export default function OutlinePopover({
  open,
  onClose,
  onSelect,
  chapters,
  selection,
  onReorder,
  onRename,
  onRegenerate,
  onDelete,
  onAddChapter,
  dragDisabled,
}: Props) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  function select(s: OutlineSelection) {
    onSelect(s);
    onClose();
  }

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-[45] cursor-default bg-slate-900/25 backdrop-blur-[2px]"
        aria-label="关闭目录"
        onClick={onClose}
      />
      <div
        className="outline-popover fixed left-[4.75rem] top-[5.25rem] z-50 flex h-[min(400px,calc(100vh-8.5rem))] w-[min(100vw-6rem,320px)] flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-3 shadow-[0_24px_60px_rgba(15,23,42,0.18)]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="outline-popover-title"
      >
        <div className="mb-2 flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 pb-2">
          <div className="flex items-baseline gap-2">
            <h2 id="outline-popover-title" className="text-sm font-semibold text-ink">
              目录
            </h2>
            <span className="text-xs tabular-nums text-slate-400">{chapters.length} 章</span>
          </div>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            onClick={onClose}
            title="关闭"
            aria-label="关闭目录"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <OutlineNavBody
            chapters={chapters}
            selection={selection}
            onSelect={select}
            onReorder={onReorder}
            onRename={onRename}
            onRegenerate={onRegenerate}
            onDelete={onDelete}
            onAddChapter={() => {
              onAddChapter();
              onClose();
            }}
            dragDisabled={dragDisabled}
          />
        </div>
      </div>
    </>
  );
}
