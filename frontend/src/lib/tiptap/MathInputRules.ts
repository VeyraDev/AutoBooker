import { Extension, InputRule } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";
import { NodeSelection } from "@tiptap/pm/state";

import { normalizeLatexInput, pastedTextLooksLikeMath } from "@/lib/latexNormalize";

const mathKeyboardPlugin = new Plugin({
  props: {
    handleKeyDown(view, event) {
      if (event.key !== "Backspace" && event.key !== "Delete") return false;
      const { selection } = view.state;
      if (!(selection instanceof NodeSelection)) return false;
      const name = selection.node.type.name;
      if (name !== "mathInline" && name !== "mathBlock") return false;
      view.dispatch(view.state.tr.deleteSelection());
      return true;
    },
  },
});

/** 输入 $...$ / $$...$$ 时自动转为 math 节点（不依赖 TipTap 默认数学扩展）。 */
export const MathInputRules = Extension.create({
  name: "mathInputRules",

  addInputRules() {
    return [
      new InputRule({
        find: /\$\$([^$\n]+?)\$\$$/,
        handler: ({ range, match, chain }) => {
          const latex = normalizeLatexInput(`$$${match[1]}$$`).latex;
          if (!latex) return null;
          chain()
            .focus()
            .deleteRange(range)
            .insertBlockMath({ latex, numbered: false, equationNumber: "", label: "" })
            .run();
        },
      }),
      new InputRule({
        find: /(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)$/,
        handler: ({ range, match, chain }) => {
          const latex = normalizeLatexInput(`$${match[1]}$`).latex;
          if (!latex) return null;
          chain().focus().deleteRange(range).insertInlineMath({ latex }).run();
        },
      }),
      new InputRule({
        find: /\\\[([\s\S]+?)\\\]$/,
        handler: ({ range, match, chain }) => {
          const latex = normalizeLatexInput(`\\[${match[1]}\\]`).latex;
          if (!latex) return null;
          chain()
            .focus()
            .deleteRange(range)
            .insertBlockMath({ latex, numbered: false, equationNumber: "", label: "" })
            .run();
        },
      }),
      new InputRule({
        find: /\\\((.+?)\\\)$/,
        handler: ({ range, match, chain }) => {
          const latex = normalizeLatexInput(`\\(${match[1]}\\)`).latex;
          if (!latex) return null;
          chain().focus().deleteRange(range).insertInlineMath({ latex }).run();
        },
      }),
    ];
  },

  addProseMirrorPlugins() {
    return [
      mathKeyboardPlugin,
      new Plugin({
        props: {
          handlePaste: (view, event) => {
            const text = event.clipboardData?.getData("text/plain")?.trim();
            if (!text || !pastedTextLooksLikeMath(text)) return false;
            const norm = normalizeLatexInput(text);
            if (!norm.latex) return false;
            event.preventDefault();
            const { tr } = view.state;
            const node =
              norm.kind === "block"
                ? view.state.schema.nodes.mathBlock.create({
                    latex: norm.latex,
                    numbered: norm.numbered,
                    equationNumber: norm.equationNumber,
                    label: norm.label,
                  })
                : view.state.schema.nodes.mathInline.create({ latex: norm.latex });
            view.dispatch(tr.replaceSelectionWith(node));
            return true;
          },
          handleDOMEvents: {
            copy: (view, event) => {
              const { from, to } = view.state.selection;
              if (from === to) return false;
              const node = view.state.doc.nodeAt(from);
              if (!node) return false;
              if (node.type.name === "mathInline") {
                event.preventDefault();
                const latex = String(node.attrs.latex ?? "");
                event.clipboardData?.setData("text/plain", `$${latex}$`);
                return true;
              }
              if (node.type.name === "mathBlock") {
                event.preventDefault();
                const latex = String(node.attrs.latex ?? "");
                event.clipboardData?.setData("text/plain", `$$\n${latex}\n$$`);
                return true;
              }
              return false;
            },
          },
        },
      }),
    ];
  },
});
