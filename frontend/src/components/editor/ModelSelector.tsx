import { ChevronDown } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

import {
  aiModelOptionValue,
  formatAiModelLabel,
  isKnownAiModel,
  normalizeAiModelValue,
  type LlmModelsResponse,
} from "@/api/config";

const DEFAULT_TRIGGER =
  "input flex h-9 min-w-[9rem] max-w-[11rem] cursor-pointer items-center justify-between gap-1 py-1 pl-2 pr-2 text-xs";

export type ModelSelectorProps = {
  aiModel: string | null;
  catalog: LlmModelsResponse | undefined;
  loading?: boolean;
  onModelChange: (model: string) => void;
  className?: string;
  /** @deprecated 使用 triggerClassName */
  selectClassName?: string;
  triggerClassName?: string;
};

export default function ModelSelector({
  aiModel,
  catalog,
  loading,
  onModelChange,
  className = "relative shrink-0",
  selectClassName,
  triggerClassName = selectClassName ?? DEFAULT_TRIGGER,
}: ModelSelectorProps) {
  const normalized = normalizeAiModelValue(aiModel, catalog);
  const value = isKnownAiModel(normalized, catalog) ? normalized : catalog?.default ?? normalized;
  const hasOptions = Boolean(catalog?.providers.length);
  const displayLabel = loading
    ? "加载模型…"
    : hasOptions
      ? formatAiModelLabel(value, catalog)
      : "未配置 LLM";

  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuStyle, setMenuStyle] = useState<CSSProperties>({});

  const positionMenu = useCallback(() => {
    const el = triggerRef.current;
    if (!el || typeof window === "undefined") return;
    const rect = el.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom - 8;
    const spaceAbove = rect.top - 8;
    const preferredMax = 280;
    let menuMaxH = Math.min(preferredMax, spaceBelow);
    let top = rect.bottom + 4;
    if (menuMaxH < 160 && spaceAbove > spaceBelow) {
      menuMaxH = Math.min(preferredMax, spaceAbove);
      top = Math.max(8, rect.top - menuMaxH - 4);
    }
    setMenuStyle({
      position: "fixed",
      top,
      left: Math.min(rect.left, window.innerWidth - 288),
      minWidth: Math.max(rect.width, 200),
      maxWidth: 280,
      maxHeight: Math.max(menuMaxH, 120),
      overflowY: "auto",
    });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    positionMenu();
  }, [open, positionMenu]);

  useEffect(() => {
    if (!open) return;
    const onScroll = (e: Event) => {
      const menuEl = menuRef.current;
      if (menuEl && e.target instanceof Node && menuEl.contains(e.target)) return;
      positionMenu();
    };
    const onResize = () => positionMenu();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const stopWheelBubble = (e: WheelEvent) => {
      const menuEl = menuRef.current;
      if (menuEl && menuEl.contains(e.target as Node)) {
        e.stopPropagation();
      }
    };
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onResize);
    window.addEventListener("keydown", onKey);
    window.addEventListener("wheel", stopWheelBubble, { capture: true, passive: false });
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("wheel", stopWheelBubble, { capture: true });
    };
  }, [open, positionMenu]);

  function pick(optionValue: string) {
    onModelChange(optionValue);
    setOpen(false);
  }

  return (
    <div className={className}>
      <button
        ref={triggerRef}
        type="button"
        className={triggerClassName}
        disabled={loading || !hasOptions}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label="模型选择"
        title={displayLabel}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="min-w-0 flex-1 truncate text-left">{displayLabel}</span>
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden
        />
      </button>

      {typeof document !== "undefined" &&
        open &&
        hasOptions &&
        createPortal(
          <>
            <div className="fixed inset-0 z-[200] bg-transparent" aria-hidden onClick={() => setOpen(false)} />
            <div
              ref={menuRef}
              role="listbox"
              aria-label="可选模型"
              style={menuStyle}
              className="model-selector-menu z-[210] overflow-y-auto overscroll-y-contain rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
              onWheel={(e) => e.stopPropagation()}
            >
              {catalog!.providers.map((provider) => (
                <div key={provider.id}>
                  <div className="sticky top-0 z-[1] bg-slate-50/95 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500 backdrop-blur-sm">
                    {provider.region === "cn" ? `国内 · ${provider.label}` : `国外 · ${provider.label}`}
                  </div>
                  {provider.models.map((model) => {
                    const optionValue = aiModelOptionValue(provider, model);
                    const selected = optionValue === value;
                    return (
                      <button
                        key={optionValue}
                        type="button"
                        role="option"
                        aria-selected={selected}
                        className={`block w-full px-3 py-2 text-left text-xs transition hover:bg-slate-50 ${
                          selected ? "bg-violet-50 font-medium text-violet-900" : "text-ink"
                        }`}
                        onClick={() => pick(optionValue)}
                      >
                        {model.label}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </>,
          document.body,
        )}
    </div>
  );
}
