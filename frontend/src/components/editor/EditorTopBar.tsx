import { ChevronLeft, ChevronDown } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import toast from "react-hot-toast";

const MODEL_OPTIONS = ["qwen-max", "qwen-turbo", "qwen-plus"];

export type AutoSaveUi = "idle" | "pending" | "saved" | "error";

export type EditorTopBarProps = {
  title: string;
  currentWords: number;
  targetWords: number;
  aiModel: string | null;
  onTitleSave: (title: string) => void;
  onModelChange: (model: string) => void;
  autoSaveStatus: AutoSaveUi;
  savedAt: Date | null;
  onBack: () => void;
  /** markdown：.md；docx：Word */
  onExport?: (format: "markdown" | "docx") => void;
};

export default function EditorTopBar({
  title,
  currentWords,
  targetWords,
  aiModel,
  onTitleSave,
  onModelChange,
  autoSaveStatus,
  savedAt,
  onBack,
  onExport,
}: EditorTopBarProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const [exportOpen, setExportOpen] = useState(false);
  const exportTriggerRef = useRef<HTMLButtonElement>(null);
  const [exportMenuStyle, setExportMenuStyle] = useState<CSSProperties>({});

  const positionExportMenu = useCallback(() => {
    const el = exportTriggerRef.current;
    if (!el || typeof window === "undefined") return;
    const rect = el.getBoundingClientRect();
    setExportMenuStyle({
      position: "fixed",
      top: rect.bottom + 6,
      right: Math.max(8, window.innerWidth - rect.right),
      minWidth: "11rem",
    });
  }, []);

  useLayoutEffect(() => {
    if (!exportOpen) return;
    positionExportMenu();
  }, [exportOpen, positionExportMenu]);

  useEffect(() => {
    if (!exportOpen) return;
    const onScroll = () => positionExportMenu();
    const onResize = () => positionExportMenu();
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onResize);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExportOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("keydown", onKey);
    };
  }, [exportOpen, positionExportMenu]);

  useEffect(() => {
    setDraft(title);
  }, [title]);

  const pct = targetWords > 0 ? Math.min(100, Math.round((currentWords / targetWords) * 100)) : 0;

  function commitTitle() {
    const t = draft.trim();
    if (!t) {
      toast.error("书名不能为空");
      setDraft(title);
      setEditing(false);
      return;
    }
    if (t !== title) onTitleSave(t);
    setEditing(false);
  }

  const saveLabel =
    autoSaveStatus === "pending"
      ? "保存中…"
      : autoSaveStatus === "saved" && savedAt
        ? `已保存 ${savedAt.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`
        : autoSaveStatus === "error"
          ? "保存失败"
          : null;

  return (
    <header className="editor-topbar-compact editor-topbar-compact--dense">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button type="button" className="icon-button shrink-0" title="返回" onClick={onBack} aria-label="返回">
          <ChevronLeft className="h-5 w-5" />
        </button>
        {editing ? (
          <input
            className="input max-w-md py-1 text-base font-medium"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitTitle}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitTitle();
              if (e.key === "Escape") {
                setDraft(title);
                setEditing(false);
              }
            }}
            autoFocus
          />
        ) : (
          <button
            type="button"
            className="truncate text-left text-lg font-medium text-ink hover:text-brand-700"
            title="点击重命名"
            onClick={() => setEditing(true)}
          >
            {title || "未命名书稿"}
          </button>
        )}
      </div>

      <div className="hidden min-w-0 flex-[2] items-center gap-3 px-4 md:flex">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500 transition-[width]"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="shrink-0 text-xs tabular-nums text-slate-600">
          {currentWords.toLocaleString()} / {targetWords.toLocaleString()} 字
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <div className="relative">
          <select
            className="input h-10 cursor-pointer appearance-none py-1 pl-3 pr-8 text-sm"
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
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        </div>

        <div className="relative">
          <button
            ref={exportTriggerRef}
            type="button"
            className="btn-secondary h-10 px-3 text-xs"
            aria-expanded={exportOpen}
            aria-haspopup="menu"
            onClick={() => setExportOpen((v) => !v)}
          >
            导出 ▾
          </button>
          {typeof document !== "undefined" &&
            exportOpen &&
            createPortal(
              <>
                <div
                  className="fixed inset-0 z-[200] bg-transparent"
                  aria-hidden
                  onClick={() => setExportOpen(false)}
                />
                <div
                  role="menu"
                  style={exportMenuStyle}
                  className="z-[210] rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
                >
                  <button
                    type="button"
                    role="menuitem"
                    className="block w-full px-3 py-2 text-left text-xs text-ink hover:bg-slate-50"
                    onClick={() => {
                      onExport?.("markdown");
                      setExportOpen(false);
                    }}
                  >
                    Markdown (.md)
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className="block w-full px-3 py-2 text-left text-xs text-ink hover:bg-slate-50"
                    onClick={() => {
                      onExport?.("docx");
                      setExportOpen(false);
                    }}
                  >
                    Word (.docx)
                  </button>
                </div>
              </>,
              document.body,
            )}
        </div>

        {saveLabel ? (
          <span className="hidden max-w-[140px] truncate text-[11px] text-slate-500 lg:inline" title={saveLabel}>
            {saveLabel}
          </span>
        ) : null}
      </div>
    </header>
  );
}
