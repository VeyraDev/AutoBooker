import { Node, mergeAttributes } from "@tiptap/core";
import katex from "katex";

function renderKatex(latex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(latex, { displayMode, throwOnError: false });
  } catch {
    return latex;
  }
}

export const MathInline = Node.create({
  name: "mathInline",
  group: "inline",
  inline: true,
  atom: true,
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
          latex: (el as HTMLElement).getAttribute("data-latex") ?? "",
        }),
      },
    ];
  },
  renderHTML({ node, HTMLAttributes }) {
    const latex = String(node.attrs.latex ?? "");
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-type": "math-inline",
        "data-latex": latex,
        class: "math-inline",
      }),
      ["span", { class: "math-inline-inner" }, 0],
    ];
  },
  addNodeView() {
    return ({ node }) => {
      const dom = document.createElement("span");
      dom.className = "math-inline";
      dom.setAttribute("data-type", "math-inline");
      const inner = document.createElement("span");
      inner.className = "math-inline-inner";
      inner.innerHTML = renderKatex(String(node.attrs.latex ?? ""), false);
      dom.append(inner);
      return { dom };
    };
  },
});

export const MathBlock = Node.create({
  name: "mathBlock",
  group: "block",
  atom: true,
  addAttributes() {
    return {
      latex: { default: "" },
    };
  },
  parseHTML() {
    return [
      {
        tag: 'div[data-type="math-block"]',
        getAttrs: (el) => ({
          latex: (el as HTMLElement).getAttribute("data-latex") ?? "",
        }),
      },
    ];
  },
  renderHTML({ node, HTMLAttributes }) {
    const latex = String(node.attrs.latex ?? "");
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-type": "math-block",
        "data-latex": latex,
        class: "math-block",
      }),
      ["div", { class: "math-block-inner" }, 0],
    ];
  },
  addNodeView() {
    return ({ node }) => {
      const dom = document.createElement("div");
      dom.className = "math-block my-3 overflow-x-auto";
      dom.setAttribute("data-type", "math-block");
      const inner = document.createElement("div");
      inner.className = "math-block-inner text-center";
      inner.innerHTML = renderKatex(String(node.attrs.latex ?? ""), true);
      dom.append(inner);
      return { dom };
    };
  },
});
