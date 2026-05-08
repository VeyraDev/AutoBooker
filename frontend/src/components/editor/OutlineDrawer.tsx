import { X } from "lucide-react";
import { createPortal } from "react-dom";

type Props = {
  open: boolean;
  title?: string;
  onClose: () => void;
  children: React.ReactNode;
};

/** 全屏大纲编辑抽屉，不卸载写作区编辑器实例 */
export default function OutlineDrawer({ open, title = "大纲预览", onClose, children }: Props) {
  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="outline-drawer-overlay fixed inset-0 z-[300] flex flex-col bg-[color-mix(in_srgb,var(--bg-page)_92%,white)] backdrop-blur-lg">
      <header className="flex shrink-0 items-center justify-between border-b border-slate-200/80 px-4 py-3 shadow-sm">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        <button type="button" className="icon-button h-10 w-10" aria-label="关闭" title="关闭" onClick={onClose}>
          <X className="h-5 w-5" />
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-4 py-6">{children}</div>
    </div>,
    document.body,
  );
}
