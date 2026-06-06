import Paragraph from "@tiptap/extension-paragraph";
import { Plugin } from "@tiptap/pm/state";

function makeParagraphId() {
  const rand = Math.random().toString(36).slice(2, 8);
  return `p_${Date.now().toString(36)}_${rand}`;
}

export const ParagraphWithId = Paragraph.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      paragraphId: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-pid"),
        renderHTML: (attributes) => {
          if (!attributes.paragraphId) return {};
          return { "data-pid": attributes.paragraphId };
        },
      },
    };
  },

  addProseMirrorPlugins() {
    return [
      new Plugin({
        appendTransaction: (_transactions, _oldState, newState) => {
          let tr = newState.tr;
          let changed = false;
          const seen = new Set<string>();
          newState.doc.descendants((node, pos) => {
            if (node.type.name !== this.name) return;
            const pid = String(node.attrs.paragraphId || "");
            if (!pid || seen.has(pid)) {
              tr = tr.setNodeMarkup(pos, undefined, { ...node.attrs, paragraphId: makeParagraphId() });
              changed = true;
              return;
            }
            seen.add(pid);
          });
          return changed ? tr : null;
        },
      }),
    ];
  },
});
