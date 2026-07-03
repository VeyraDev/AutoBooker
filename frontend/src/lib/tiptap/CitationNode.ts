import { Node, mergeAttributes } from "@tiptap/core";

export type CitationNodeAttrs = {
  nodeId: string;
  citationId: string;
  evidenceId: string;
  citeMode: string;
  locator: string;
  prefix: string;
  suffix: string;
  renderedText: string;
  displayText: string;
};

export const CitationNode = Node.create({
  name: "citation",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,

  addAttributes() {
    return {
      nodeId: { default: "" },
      citationId: { default: "" },
      evidenceId: { default: "" },
      citeMode: { default: "parenthetical" },
      locator: { default: "" },
      prefix: { default: "" },
      suffix: { default: "" },
      renderedText: { default: "（引用）" },
      displayText: { default: "[?]" },
    };
  },

  parseHTML() {
    return [{ tag: "span[data-citation-id]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-citation-id": HTMLAttributes.citationId,
        "data-citation-node-id": HTMLAttributes.nodeId,
        "data-citation-rendered-text": HTMLAttributes.renderedText,
        class: "citation-node",
        contenteditable: "false",
        title: HTMLAttributes.renderedText || "引用",
      }),
      HTMLAttributes.displayText || HTMLAttributes.renderedText || "[?]",
    ];
  },

  renderText({ node }) {
    return String(node.attrs.displayText || node.attrs.renderedText || "[?]");
  },
});
