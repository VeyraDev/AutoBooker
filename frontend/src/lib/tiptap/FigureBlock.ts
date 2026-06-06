import { Node, mergeAttributes } from "@tiptap/core";
import { ReactNodeViewRenderer } from "@tiptap/react";

import FigureBlockView from "@/components/editor/FigureBlockView";
import type { FigureStatus, FigureType } from "@/api/figures";

export type FigureBlockAttrs = {
  figureId: string;
  figureType: FigureType;
  figureNumber: string;
  caption: string;
  status: FigureStatus;
  fileUrl: string;
  svgUrl: string;
  rawAnnotation: string;
  /** 毫秒时间戳，用于破坏浏览器对同路径 PNG 的缓存 */
  fileVersion: number;
};

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    figureBlock: {
      insertFigureBlock: (attrs: Partial<FigureBlockAttrs>) => ReturnType;
      updateFigureBlockAttrs: (figureId: string, patch: Partial<FigureBlockAttrs>) => ReturnType;
    };
  }
}

export const FigureBlock = Node.create({
  name: "figureBlock",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      figureId: { default: "" },
      figureType: { default: "figure" as FigureType },
      figureNumber: { default: "" },
      caption: { default: "" },
      status: { default: "pending" as FigureStatus },
      fileUrl: { default: "" },
      svgUrl: { default: "" },
      rawAnnotation: { default: "" },
      fileVersion: {
        default: 0,
        parseHTML: (el) => Number((el as HTMLElement).getAttribute("data-file-version")) || 0,
        renderHTML: (attrs) =>
          attrs.fileVersion ? { "data-file-version": String(attrs.fileVersion) } : {},
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'div[data-type="figure-block"]',
        getAttrs: (el) => {
          const node = el as HTMLElement;
          return {
            figureId: node.getAttribute("data-figure-id") ?? "",
            figureType: node.getAttribute("data-figure-type") ?? "figure",
            figureNumber: node.getAttribute("data-figure-number") ?? "",
            caption: node.getAttribute("data-caption") ?? "",
            status: node.getAttribute("data-status") ?? "pending",
            fileUrl: node.getAttribute("data-file-url") ?? "",
            svgUrl: node.getAttribute("data-svg-url") ?? "",
            rawAnnotation: node.getAttribute("data-raw-annotation") ?? "",
            fileVersion: Number(node.getAttribute("data-file-version") || 0),
          };
        },
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes, { "data-type": "figure-block" })];
  },

  addNodeView() {
    return ReactNodeViewRenderer(FigureBlockView);
  },

  addCommands() {
    return {
      insertFigureBlock:
        (attrs: Partial<FigureBlockAttrs>) =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs: {
              figureId: attrs.figureId ?? "",
              figureType: attrs.figureType ?? "figure",
              figureNumber: attrs.figureNumber ?? "",
              caption: attrs.caption ?? "",
              status: attrs.status ?? "pending",
              fileUrl: attrs.fileUrl ?? "",
              svgUrl: attrs.svgUrl ?? "",
              rawAnnotation: attrs.rawAnnotation ?? "",
              fileVersion: attrs.fileVersion ?? 0,
            },
          }),
      updateFigureBlockAttrs:
        (figureId: string, patch: Partial<FigureBlockAttrs>) =>
        ({ tr, state, dispatch }) => {
          let changed = false;
          state.doc.descendants((node, pos) => {
            if (node.type.name !== "figureBlock") return;
            if (node.attrs.figureId !== figureId) return;
            tr.setNodeMarkup(pos, undefined, { ...node.attrs, ...patch });
            changed = true;
          });
          if (changed && dispatch) {
            dispatch(tr);
            return true;
          }
          return changed;
        },
    };
  },
});
