import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { FormulaEditRequest } from "@/lib/formulaEditorBridge";
import {
  LATEX_SNIPPET_GROUPS,
  applySnippetAtCursor,
  normalizeLatexInput,
  renderLatexToHtml,
} from "@/lib/latexNormalize";

type Props = {
  open: boolean;
  initial: FormulaEditRequest | null;
  onClose: () => void;
  onConfirm: (result: {
    mode: FormulaEditRequest["mode"];
    latex: string;
    pos?: number;
    nodeType?: FormulaEditRequest["nodeType"];
    numbered?: boolean;
    equationNumber?: string;
    label?: string;
  }) => void;
};

export default function FormulaEditorDialog({ open, initial, onClose, onConfirm }: Props) {
  const [rawLatex, setRawLatex] = useState("");
  const [kind, setKind] = useState<"inline" | "block">("inline");
  const [numbered, setNumbered] = useState(false);
  const [equationNumber, setEquationNumber] = useState("");
  const [label, setLabel] = useState("");
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewHtml, setPreviewHtml] = useState("");
  const [stripHint, setStripHint] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!open || !initial) return;
    setRawLatex(initial.latex || "");
    if (initial.mode === "insert-block" || initial.nodeType === "mathBlock") {
      setKind("block");
    } else {
      setKind("inline");
    }
    setNumbered(Boolean(initial.numbered));
    setEquationNumber(initial.equationNumber || "");
    setLabel(initial.label || "");
    setPreviewError(null);
    setStripHint("");
    requestAnimationFrame(() => textareaRef.current?.focus());
  }, [open, initial]);

  const normalized = useMemo(
    () =>
      normalizeLatexInput(rawLatex, {
        preferKind: kind,
        keepExistingNumber: { numbered, equationNumber, label },
      }),
    [rawLatex, kind, numbered, equationNumber, label],
  );

  useEffect(() => {
    if (!open) return;
    if (normalized.autoDetectedBlock && kind === "inline" && rawLatex.trim()) {
      setKind("block");
    }
  }, [normalized.autoDetectedBlock, open, kind, rawLatex]);

  useEffect(() => {
    if (!open) return;
    const src = normalized.latex;
    if (!src) {
      setPreviewHtml("");
      setPreviewError(null);
      return;
    }
    const { html, error } = renderLatexToHtml(src, kind === "block");
    setPreviewHtml(html);
    setPreviewError(error);
    setStripHint(normalized.stripped.length ? `已自动去除：${normalized.stripped.join("、")}` : "");
  }, [open, normalized.latex, normalized.stripped, kind]);

  const insertSnippet = useCallback(
    (snippet: string) => {
      const ta = textareaRef.current;
      if (!ta) return;
      const { value, selectionStart, selectionEnd } = applySnippetAtCursor(
        rawLatex,
        ta.selectionStart,
        ta.selectionEnd,
        snippet,
      );
      setRawLatex(value);
      requestAnimationFrame(() => {
        ta.focus();
        ta.setSelectionRange(selectionStart, selectionEnd);
      });
    },
    [rawLatex],
  );

  const handlePaste = useCallback((e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const text = e.clipboardData.getData("text/plain");
    if (!text?.trim()) return;
    const norm = normalizeLatexInput(text, { preferKind: kind });
    if (norm.stripped.length === 0 && !norm.autoDetectedBlock) return;
    e.preventDefault();
    setRawLatex(norm.latex);
    if (norm.autoDetectedBlock) setKind("block");
    if (norm.numbered) {
      setNumbered(true);
      if (norm.equationNumber) setEquationNumber(norm.equationNumber);
    }
    if (norm.label) setLabel(norm.label);
  }, [kind]);

  const handleConfirm = useCallback(() => {
    if (!initial) return;
    const norm = normalizeLatexInput(rawLatex, {
      preferKind: kind,
      keepExistingNumber: { numbered, equationNumber, label },
    });
    if (!norm.latex.trim()) return;
    const nodeType = kind === "block" ? "mathBlock" : "mathInline";
    onConfirm({
      mode: initial.mode,
      latex: norm.latex,
      pos: initial.pos,
      nodeType,
      numbered: kind === "block" ? numbered || norm.numbered : undefined,
      equationNumber:
        kind === "block" && (numbered || norm.numbered)
          ? (equationNumber.trim() || norm.equationNumber)
          : undefined,
      label: kind === "block" && (numbered || norm.numbered) ? (label.trim() || norm.label) : undefined,
    });
    onClose();
  }, [initial, rawLatex, kind, numbered, equationNumber, label, onConfirm, onClose]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        handleConfirm();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose, handleConfirm]);

  if (!open || !initial) return null;

  const editing = initial.mode === "edit";
  const canConfirm = Boolean(normalized.latex.trim()) && !previewError;

  return createPortal(
    <div
      className="formula-editor-backdrop fixed inset-0 z-[500] flex items-center justify-center bg-black/35 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="formula-editor-panel flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-slate-200 bg-white shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="formula-editor-title"
      >
        <div className="flex shrink-0 items-center justify-between border-b border-slate-100 px-5 py-3">
          <div>
            <h2 id="formula-editor-title" className="text-base font-semibold text-ink">
              {editing ? "编辑公式" : "插入公式"}
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              可粘贴 <code className="rounded bg-slate-100 px-1">$…$</code> 或{" "}
              <code className="rounded bg-slate-100 px-1">$$…$$</code>，保存时自动转为纯 LaTeX
            </p>
          </div>
          <button type="button" className="text-xl leading-none text-slate-400 hover:text-slate-700" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
          <div className="formula-editor-symbols rounded-lg border border-slate-100 bg-slate-50/60 p-2">
            {LATEX_SNIPPET_GROUPS.map((group) => (
              <div key={group.title} className="mb-2 last:mb-0">
                <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">{group.title}</div>
                <div className="flex flex-wrap gap-1">
                  {group.items.map((item) => (
                    <button
                      key={`${group.title}-${item.label}`}
                      type="button"
                      className="formula-editor-symbol-btn rounded border border-slate-200 bg-white px-2 py-0.5 font-mono text-xs text-slate-700 hover:border-indigo-300 hover:bg-indigo-50"
                      title={item.title ?? item.latex.replace(/\{cursor\}/g, "")}
                      onClick={() => insertSnippet(item.latex)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <label className="block text-sm">
            <span className="text-slate-600">LaTeX</span>
            <textarea
              ref={textareaRef}
              className="input mt-1 min-h-[6rem] font-mono text-sm leading-relaxed"
              value={rawLatex}
              onChange={(e) => setRawLatex(e.target.value)}
              onPaste={handlePaste}
              placeholder="例如 \\frac{a+b}{c+d} 或粘贴 $$E=mc^2$$"
              spellCheck={false}
              rows={4}
            />
          </label>

          <div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">预览</span>
              {stripHint ? <span className="text-xs text-indigo-600">{stripHint}</span> : null}
            </div>
            <div
              className={`formula-editor-preview mt-1 min-h-[3.5rem] rounded-lg border px-3 py-3 text-center ${
                previewError
                  ? "border-amber-200 bg-amber-50/80"
                  : "border-slate-100 bg-slate-50/80"
              }`}
            >
              {previewError ? (
                <p className="text-left text-xs text-amber-800">
                  <span className="font-medium">KaTeX 无法解析：</span>
                  {previewError}
                </p>
              ) : null}
              <div
                dangerouslySetInnerHTML={{
                  __html:
                    previewHtml ||
                    '<span class="text-slate-400 text-sm">输入 LaTeX 后在此预览</span>',
                }}
              />
            </div>
          </div>

          <fieldset className="text-sm">
            <legend className="mb-2 text-slate-600">类型</legend>
            <label className="mr-4 inline-flex items-center gap-1.5">
              <input
                type="radio"
                name="formula-kind"
                checked={kind === "inline"}
                onChange={() => setKind("inline")}
              />
              行内公式
            </label>
            <label className="inline-flex items-center gap-1.5">
              <input
                type="radio"
                name="formula-kind"
                checked={kind === "block"}
                onChange={() => setKind("block")}
              />
              独立公式
            </label>
          </fieldset>

          {kind === "block" ? (
            <div className="space-y-2 rounded-lg border border-slate-100 bg-slate-50/50 p-3 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={numbered} onChange={(e) => setNumbered(e.target.checked)} />
                显示公式编号
              </label>
              {numbered ? (
                <>
                  <label className="block">
                    <span className="text-slate-600">编号</span>
                    <input
                      className="input mt-1"
                      value={equationNumber}
                      onChange={(e) => setEquationNumber(e.target.value)}
                      placeholder="1"
                    />
                  </label>
                  <label className="block">
                    <span className="text-slate-600">内部引用标签（可选）</span>
                    <input
                      className="input mt-1 font-mono text-xs"
                      value={label}
                      onChange={(e) => setLabel(e.target.value)}
                      placeholder="eq:cache-hit-rate"
                    />
                  </label>
                </>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center justify-between gap-2 border-t border-slate-100 px-5 py-3">
          <span className="text-xs text-slate-400">Ctrl+Enter 确认</span>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary text-sm" onClick={onClose}>
              取消
            </button>
            <button
              type="button"
              className="btn-primary text-sm"
              disabled={!canConfirm}
              onClick={handleConfirm}
            >
              确认
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
