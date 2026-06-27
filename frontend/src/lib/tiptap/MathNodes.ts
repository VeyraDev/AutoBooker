import { Node, mergeAttributes } from "@tiptap/core";

import { requestFormulaEdit, type FormulaEditRequest } from "@/lib/formulaEditorBridge";
import { normalizeLatexInput, renderLatexToHtml } from "@/lib/latexNormalize";

export type MathNodeOptions = {
  onFormulaClick?: ((req: FormulaEditRequest) => void) | null;
};

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    mathInline: {
      insertInlineMath: (attrs: { latex: string }) => ReturnType;
      updateInlineMath: (attrs: { latex: string; pos?: number }) => ReturnType;
    };
    mathBlock: {
      insertBlockMath: (attrs: {
        latex: string;
        numbered?: boolean;
        equationNumber?: string;
        label?: string;
      }) => ReturnType;
      updateBlockMath: (attrs: {
        latex: string;
        numbered?: boolean;
        equationNumber?: string;
        label?: string;
        pos?: number;
      }) => ReturnType;
    };
  }
}

function cleanLatex(raw: string): string {
  return normalizeLatexInput(raw).latex;
}

function renderKatex(latex: string, displayMode: boolean): { html: string; hasError: boolean } {
  const { html, error } = renderLatexToHtml(latex, displayMode);
  return { html, hasError: Boolean(error) };
}

function emitClick(options: MathNodeOptions, payload: FormulaEditRequest): void {
  if (options.onFormulaClick) {
    options.onFormulaClick(payload);
    return;
  }
  requestFormulaEdit(payload);
}

function openEditorFromNode(
  options: MathNodeOptions,
  editor: { isEditable: boolean },
  getPos: (() => number | undefined) | boolean,
  payload: Omit<FormulaEditRequest, "mode">,
): void {
  if (!editor.isEditable) return;
  const pos = typeof getPos === "function" ? getPos() : undefined;
  if (typeof pos !== "number") return;
  emitClick(options, { mode: "edit", ...payload, pos });
}

export const MathInline = Node.create<MathNodeOptions>({
  name: "mathInline",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,

  addOptions() {
    return { onFormulaClick: null };
  },

  addAttributes() {
    return {
      latex: { default: "" },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-type="math-inline"]',
        getAttrs: (el) => ({
          latex: cleanLatex((el as HTMLElement).getAttribute("data-latex") ?? ""),
        }),
      },
    ];
  },

  renderHTML({ node, HTMLAttributes }) {
    const latex = cleanLatex(String(node.attrs.latex ?? ""));
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-type": "math-inline",
        "data-latex": latex,
        class: "math-inline",
        contenteditable: "false",
      }),
    ];
  },

  addCommands() {
    return {
      insertInlineMath:
        (attrs) =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs: { latex: cleanLatex(attrs.latex) },
          }),
      updateInlineMath:
        (attrs) =>
        ({ tr, state, dispatch }) => {
          const pos = attrs.pos ?? state.selection.from;
          const node = state.doc.nodeAt(pos);
          if (!node || node.type.name !== this.name) return false;
          if (dispatch) {
            tr.setNodeMarkup(pos, undefined, { ...node.attrs, latex: cleanLatex(attrs.latex) });
            dispatch(tr);
          }
          return true;
        },
    };
  },

  addNodeView() {
    return ({ node, getPos, editor }) => {
      const dom = document.createElement("span");
      dom.className = "math-inline";
      dom.setAttribute("data-type", "math-inline");
      dom.setAttribute("contenteditable", "false");
      dom.title = "单击或双击编辑公式";

      const inner = document.createElement("span");
      inner.className = "math-inline-inner";
      dom.append(inner);

      const render = () => {
        const latex = cleanLatex(String(node.attrs.latex ?? ""));
        const { html, hasError } = renderKatex(latex, false);
        inner.innerHTML = html;
        dom.classList.toggle("math-inline--error", hasError);
      };
      render();

      const onEdit = (e: Event) => {
        e.preventDefault();
        e.stopPropagation();
        openEditorFromNode(this.options, editor, getPos, {
          latex: String(node.attrs.latex ?? ""),
          nodeType: "mathInline",
        });
      };
      dom.addEventListener("click", onEdit);
      dom.addEventListener("dblclick", onEdit);

      return {
        dom,
        update: (updated) => {
          if (updated.type.name !== this.name) return false;
          node = updated;
          render();
          return true;
        },
      };
    };
  },
});

export const MathBlock = Node.create<MathNodeOptions>({
  name: "mathBlock",
  group: "block",
  atom: true,
  selectable: true,

  addOptions() {
    return { onFormulaClick: null };
  },

  addAttributes() {
    return {
      latex: { default: "" },
      numbered: { default: false },
      equationNumber: { default: "" },
      label: { default: "" },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'div[data-type="math-block"]',
        getAttrs: (el) => {
          const html = el as HTMLElement;
          const norm = normalizeLatexInput(html.getAttribute("data-latex") ?? "");
          return {
            latex: norm.latex,
            numbered: html.getAttribute("data-numbered") === "true" || norm.numbered,
            equationNumber: html.getAttribute("data-equation-number") ?? norm.equationNumber,
            label: html.getAttribute("data-label") ?? norm.label,
          };
        },
      },
    ];
  },

  renderHTML({ node, HTMLAttributes }) {
    const latex = cleanLatex(String(node.attrs.latex ?? ""));
    const numbered = Boolean(node.attrs.numbered);
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-type": "math-block",
        "data-latex": latex,
        "data-numbered": numbered ? "true" : "false",
        "data-equation-number": String(node.attrs.equationNumber ?? ""),
        "data-label": String(node.attrs.label ?? ""),
        class: "math-block",
        contenteditable: "false",
      }),
    ];
  },

  addCommands() {
    return {
      insertBlockMath:
        (attrs) =>
        ({ commands }) => {
          const norm = normalizeLatexInput(attrs.latex, { preferKind: "block" });
          return commands.insertContent({
            type: this.name,
            attrs: {
              latex: norm.latex,
              numbered: attrs.numbered ?? norm.numbered ?? false,
              equationNumber: attrs.equationNumber ?? norm.equationNumber ?? "",
              label: attrs.label ?? norm.label ?? "",
            },
          });
        },
      updateBlockMath:
        (attrs) =>
        ({ tr, state, dispatch }) => {
          const pos = attrs.pos ?? state.selection.from;
          const node = state.doc.nodeAt(pos);
          if (!node || node.type.name !== this.name) return false;
          const norm = normalizeLatexInput(attrs.latex, { preferKind: "block" });
          if (dispatch) {
            tr.setNodeMarkup(pos, undefined, {
              ...node.attrs,
              latex: norm.latex,
              numbered: attrs.numbered ?? node.attrs.numbered,
              equationNumber: attrs.equationNumber ?? node.attrs.equationNumber,
              label: attrs.label ?? node.attrs.label,
            });
            dispatch(tr);
          }
          return true;
        },
    };
  },

  addNodeView() {
    return ({ node, getPos, editor }) => {
      const dom = document.createElement("div");
      dom.className = "math-block";
      dom.setAttribute("data-type", "math-block");
      dom.setAttribute("contenteditable", "false");
      dom.title = "单击或双击编辑公式";

      const inner = document.createElement("div");
      inner.className = "math-block-inner";
      const numEl = document.createElement("span");
      numEl.className = "math-block-number";
      const wrap = document.createElement("div");
      wrap.className = "math-block-wrap";
      wrap.append(inner, numEl);
      dom.append(wrap);

      const render = () => {
        const latex = cleanLatex(String(node.attrs.latex ?? ""));
        const { html, hasError } = renderKatex(latex, true);
        inner.innerHTML = html;
        dom.classList.toggle("math-block--error", hasError);
        const numbered = Boolean(node.attrs.numbered);
        const num = String(node.attrs.equationNumber ?? "").trim();
        if (numbered && num) {
          numEl.textContent = `(${num})`;
          numEl.style.display = "";
          wrap.classList.add("math-block-wrap--numbered");
        } else {
          numEl.textContent = "";
          numEl.style.display = "none";
          wrap.classList.remove("math-block-wrap--numbered");
        }
      };
      render();

      const onEdit = (e: Event) => {
        e.preventDefault();
        e.stopPropagation();
        openEditorFromNode(this.options, editor, getPos, {
          latex: String(node.attrs.latex ?? ""),
          nodeType: "mathBlock",
          numbered: Boolean(node.attrs.numbered),
          equationNumber: String(node.attrs.equationNumber ?? ""),
          label: String(node.attrs.label ?? ""),
        });
      };
      dom.addEventListener("click", onEdit);
      dom.addEventListener("dblclick", onEdit);

      return {
        dom,
        update: (updated) => {
          if (updated.type.name !== this.name) return false;
          node = updated;
          render();
          return true;
        },
      };
    };
  },
});
