import { Extension } from "@tiptap/core";
import { Plugin, PluginKey, type EditorState } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

import type { AiPreviewKind } from "@/types/aiPreview";
export type AiInlinePreviewData = {
  from: number;
  to: number;
  quote: string;
  suggestion: string;
  kind: AiPreviewKind;
};

export const aiInlinePreviewKey = new PluginKey<AiInlinePreviewData | null>("aiInlinePreview");

function mapPreview(
  prev: AiInlinePreviewData,
  mapping: import("@tiptap/pm/transform").Mapping,
): AiInlinePreviewData | null {
  const from = mapping.map(prev.from, -1);
  const to = mapping.map(prev.to, 1);
  if (from == null || to == null) return null;
  return { ...prev, from, to };
}

function buildDecorations(state: EditorState, preview: AiInlinePreviewData): DecorationSet {
  const decos: Decoration[] = [];

  if (preview.kind === "replace" && preview.to > preview.from) {
    decos.push(
      Decoration.inline(preview.from, preview.to, {
        class: "ai-inline-source",
      }),
    );
  } else if (preview.kind === "insert") {
    decos.push(
      Decoration.inline(preview.from, preview.to, {
        class: "ai-inline-insert-marker",
      }),
    );
  }

  const widget = document.createElement("div");
  widget.className = "ai-inline-widget";
  widget.contentEditable = "false";

  const toolbar = document.createElement("div");
  toolbar.className = "ai-inline-toolbar";

  const acceptBtn = document.createElement("button");
  acceptBtn.type = "button";
  acceptBtn.className = "ai-inline-btn ai-inline-btn-accept";
  acceptBtn.textContent = "应用";
  acceptBtn.dataset.aiAction = "accept";

  const rejectBtn = document.createElement("button");
  rejectBtn.type = "button";
  rejectBtn.className = "ai-inline-btn ai-inline-btn-reject";
  rejectBtn.textContent = "取消";
  rejectBtn.dataset.aiAction = "reject";

  toolbar.append(acceptBtn, rejectBtn);

  const body = document.createElement("div");
  body.className =
    preview.kind === "insert"
      ? "ai-inline-body ai-inline-text-insert"
      : "ai-inline-body ai-inline-text-replace";
  const pre = document.createElement("div");
  pre.className = "ai-inline-text";
  pre.textContent = preview.suggestion;
  body.appendChild(pre);

  widget.append(toolbar, body);

  decos.push(
    Decoration.widget(preview.to, widget, {
      side: 1,
      key: `ai-suggestion-${preview.from}-${preview.to}`,
    }),
  );

  return DecorationSet.create(state.doc, decos);
}

export type AiInlinePreviewOptions = {
  onAccept: () => void;
  onReject: () => void;
};

export const AiInlinePreview = Extension.create<AiInlinePreviewOptions>({
  name: "aiInlinePreview",

  addOptions() {
    return {
      onAccept: () => {},
      onReject: () => {},
    };
  },

  addProseMirrorPlugins() {
    const { onAccept, onReject } = this.options;
    return [
      new Plugin({
        key: aiInlinePreviewKey,
        state: {
          init: () => null as AiInlinePreviewData | null,
          apply(tr, value) {
            const meta = tr.getMeta(aiInlinePreviewKey) as AiInlinePreviewData | null | undefined;
            if (meta !== undefined) return meta;
            if (value && tr.docChanged) {
              return mapPreview(value, tr.mapping);
            }
            return value;
          },
        },
        props: {
          decorations(state) {
            const preview = aiInlinePreviewKey.getState(state);
            if (!preview) return DecorationSet.empty;
            return buildDecorations(state, preview);
          },
          handleDOMEvents: {
            click(_view, event) {
              const target = event.target as HTMLElement;
              const btn = target.closest("[data-ai-action]") as HTMLElement | null;
              if (!btn) return false;
              const action = btn.dataset.aiAction;
              if (action === "accept") {
                onAccept();
                return true;
              }
              if (action === "reject") {
                onReject();
                return true;
              }
              return false;
            },
          },
        },
      }),
    ];
  },

  addCommands() {
    return {
      setAiInlinePreview:
        (data: AiInlinePreviewData) =>
        ({ tr, dispatch }) => {
          if (dispatch) {
            dispatch(tr.setMeta(aiInlinePreviewKey, data));
          }
          return true;
        },
      clearAiInlinePreview:
        () =>
        ({ tr, dispatch }) => {
          if (dispatch) {
            dispatch(tr.setMeta(aiInlinePreviewKey, null));
          }
          return true;
        },
    };
  },
});

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    aiInlinePreview: {
      setAiInlinePreview: (data: AiInlinePreviewData) => ReturnType;
      clearAiInlinePreview: () => ReturnType;
    };
  }
}
