import { BubbleMenu, EditorContent, useEditor } from "@tiptap/react";
import type { Editor } from "@tiptap/core";
import { isTextSelection } from "@tiptap/core";
import { Bold, Loader2, MoreHorizontal } from "lucide-react";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import toast from "react-hot-toast";

import { TextSelection, type EditorState } from "@tiptap/pm/state";
import type { EditorView } from "@tiptap/pm/view";

import EditorErrorBoundary from "@/components/common/EditorErrorBoundary";
import { ANNOTATION_TEST_RE } from "@/lib/annotationPatterns";
import {
  figureFileVersion,
  refreshChapterFigures,
  syncChapterFigures,
  type FigureStatus,
  type FigureType,
} from "@/api/figures";
import { editChapterSelection, type SelectionEditMode } from "@/api/chapters";
import { FigureBlockContext } from "@/contexts/FigureBlockContext";
import { getChapterEditorExtensions } from "@/lib/chapterEditorExtensions";
import { aiInlinePreviewKey, type AiInlinePreviewData } from "@/lib/tiptap/AiInlinePreview";
import {
  buildTiptapDocWithFigures,
  enrichSyncedTiptapDoc,
  extractFigureBlocksFromDoc,
  tiptapHasFigureBlocks,
  tiptapHasRichStructure,
  tiptapMissingMarkdownFeatures,
} from "@/lib/buildTiptapDocWithFigures";
import { cleanSuggestionText } from "@/lib/cleanSuggestion";
import { migrateTiptapDoc } from "@/lib/migrateTiptapDoc";
import type { EditorAiPreviewPayload } from "@/types/aiPreview";
import { resolveChapterEditorContent } from "@/lib/resolveChapterEditorContent";
import { tiptapDocToMarkdown } from "@/lib/tiptapDocToMarkdown";
import { isRichMarkdown, markdownToTiptapDoc } from "@/lib/markdownToTiptapDoc";
import { normalizeGfmMarkdown } from "@/lib/normalizeGfmMarkdown";
import { plainTextMarkdownToTiptapDoc, shouldParseAsMarkdown } from "@/lib/plainTextMarkdownToTiptap";
import type { Chapter } from "@/types/chapter";

export type ChapterEditorHandle = {
  appendText: (t: string) => void;
  clear: () => void;
  applyPlainMarkdown: (raw: string) => void;
  /** 应用服务端已组装的章节内容（优先 tiptap_json） */
  applyServerContent: (content: Record<string, unknown> | null | undefined) => void;
  scrollToSectionAnchor: (anchorId: string) => boolean;
  getSerialized: () => { json: Record<string, unknown>; text: string } | null;
  insertReferenceQuote: (body: string, filename: string) => void;
  insertCitationMarks: (marks: string[]) => void;
  insertLiteratureQuotes: (quotes: { quote_body: string; bibliography_line?: string }[]) => void;
  replaceQuoteWithSuggestion: (quote: string, suggestion: string) => boolean;
  getSelectionPlain: () => string;
  getChapterContextAroundSelection: (maxChars?: number) => string;
  showAiPreview: (payload: EditorAiPreviewPayload) => boolean;
  confirmAiPreview: () => boolean;
  dismissAiPreview: () => void;
  hasAiPreview: () => boolean;
  focusEditor: () => void;
  applySyncedDoc: (doc: Record<string, unknown>, markdownText?: string) => void;
  updateFigureBlock: (figureId: string, patch: Record<string, unknown>) => void;
  insertFigureBlock: (attrs: Record<string, unknown>) => void;
  applyFigureResult: (
    fig: {
      figure_id: string;
      file_url: string | null;
      figure_number: string | null;
      status: string;
      caption: string | null;
      figure_type: string;
      updated_at?: string | null;
    },
    options?: { replaceOnly?: boolean; targetFigureId?: string },
  ) => void;
};

type Props = {
  chapter: Chapter;
  readOnly: boolean;
  bookId: string;
  chapterIndex: number;
  /** 非 null 且只读时：用 GFM 渲染流式正文（不写入 TipTap DOM） */
  streamingMarkdown: string | null;
  onChange: (payload: { json: Record<string, unknown>; text: string; characters: number }) => void;
  onOpenAssistantPanel?: (selectedPlain: string) => void;
  onQuoteFigure?: (figureId: string, annotation: string) => void;
  onSelectionChange?: (plain: string) => void;
};

const EMPTY_DOC: Record<string, unknown> = { type: "doc", content: [] };

function initialContent(ch: Chapter): string | Record<string, unknown> {
  try {
    const c = ch.content as Record<string, unknown> | null | undefined;
    if (!c) return "";
    return resolveChapterEditorContent(c);
  } catch {
    return EMPTY_DOC;
  }
}

const ChapterTiptapEditor = forwardRef<ChapterEditorHandle, Props>(function ChapterTiptapEditor(
  { chapter, readOnly, bookId, chapterIndex, streamingMarkdown, onChange, onOpenAssistantPanel, onQuoteFigure, onSelectionChange },
  ref,
) {
  const [aiBusy, setAiBusy] = useState<SelectionEditMode | null>(null);
  const [headingMenuOpen, setHeadingMenuOpen] = useState(false);
  const figureSyncAttemptRef = useRef<string | null>(null);
  const figureSyncInFlightRef = useRef(false);
  const figureRefreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const formatRecoveredChapterRef = useRef<string | null>(null);
  const [figureDocRevision, setFigureDocRevision] = useState(0);

  /** 流式预览时整段切换为下方 ReactMarkdown（与原先 SSE 设计一致）。非预览时 BubbleMenu 用 shouldShow + ref，避免与 Tippy 冲突。 */
  const bubbleGateRef = useRef({ readOnly: false, stream: false });
  bubbleGateRef.current = { readOnly, stream: streamingMarkdown !== null };

  const previewHandlersRef = useRef({ onAccept: () => {}, onReject: () => {} });
  const extensions = useMemo(
    () =>
      getChapterEditorExtensions("从这里开始撰写本章正文…", {
        onAccept: () => previewHandlersRef.current.onAccept(),
        onReject: () => previewHandlersRef.current.onReject(),
      }),
    [],
  );

  function getChapterContextAroundSelection(maxChars = 2400): string {
    if (!editor) return "";
    const { from, to, empty } = editor.state.selection;
    const docSize = editor.state.doc.content.size;
    if (empty) return editor.getText().slice(0, maxChars);
    const half = Math.floor(maxChars / 2);
    const before = editor.state.doc.textBetween(0, from, "\n");
    const after = editor.state.doc.textBetween(to, docSize, "\n");
    const selected = editor.state.doc.textBetween(from, to, "\n");
    const b = before.length > half ? `…${before.slice(-half)}` : before;
    const a = after.length > half ? `${after.slice(0, half)}…` : after;
    return `${b}\n[选中]\n${selected}\n[/选中]\n${a}`;
  }

  function normalizeMatchText(s: string): string {
    return s.replace(/\s+/g, " ").trim();
  }

  function findTextRange(needle: string): { from: number; to: number } | null {
    if (!editor || !needle) return null;
    let found: { from: number; to: number } | null = null;
    editor.state.doc.descendants((node, pos) => {
      if (found || !node.isText || !node.text) return;
      const i = node.text.indexOf(needle);
      if (i >= 0) {
        found = { from: pos + i, to: pos + i + needle.length };
      }
    });
    return found;
  }

  function resolveQuoteRange(quote: string): { from: number; to: number } | null {
    if (!editor) return null;
    const q = quote.trim();
    if (!q) {
      const { from } = editor.state.selection;
      return { from, to: from };
    }
    const { from, to, empty } = editor.state.selection;
    const selected = empty ? "" : editor.state.doc.textBetween(from, to, "\n");
    if (!empty && normalizeMatchText(selected) === normalizeMatchText(q)) return { from, to };
    let found = findTextRange(q);
    if (!found && q.length > 24) {
      found = findTextRange(q.slice(0, Math.min(80, q.length)));
    }
    if (!found) {
      const compact = normalizeMatchText(q);
      if (compact.length >= 12) {
        editor.state.doc.descendants((node, pos) => {
          if (found || !node.isText || !node.text) return;
          const norm = normalizeMatchText(node.text);
          const i = norm.indexOf(compact);
          if (i >= 0) {
            found = { from: pos + i, to: pos + i + compact.length };
          }
        });
      }
    }
    return found;
  }

  function safeSetContent(content: string | Record<string, unknown>): void {
    if (!editor) return;
    try {
      editor.chain().setContent(content).run();
    } catch (e) {
      console.warn("[ChapterTiptapEditor] setContent failed", e);
      try {
        editor.chain().setContent(EMPTY_DOC).run();
      } catch {
        /* ignore */
      }
    }
  }

  function applyPreviewContent(preview: AiInlinePreviewData): boolean {
    if (!editor) return false;
    if (preview.kind === "insert") {
      editor.chain().focus().insertContentAt(preview.to, preview.suggestion.trim()).run();
      return true;
    }
    editor
      .chain()
      .focus()
      .deleteRange({ from: preview.from, to: preview.to })
      .insertContentAt(preview.from, preview.suggestion.trim())
      .run();
    return true;
  }

  function showInlinePreview(payload: EditorAiPreviewPayload): boolean {
    if (!editor) return false;
    const range = resolveQuoteRange(payload.quote.trim());
    if (!range) return false;
    editor.commands.setAiInlinePreview({
      ...range,
      quote: payload.quote,
      suggestion: payload.suggestion,
      kind: payload.kind,
    });
    requestAnimationFrame(() => {
      editor.view.dom.querySelector(".ai-inline-widget")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
    return true;
  }

  const editor = useEditor({
    /** React 18 StrictMode 下避免首屏双挂载导致编辑器异常或白屏（@tiptap/react 官方建议） */
    immediatelyRender: false,
    /** TipTap 默认会 rethrow，导致整页 React 崩溃白屏 */
    onContentError: ({ error }) => {
      console.warn("[ChapterTiptapEditor] contentError (已吞掉避免白屏)", error?.message ?? error);
    },
    extensions,
    editable: !readOnly,
    content: initialContent(chapter),
    editorProps: {
      attributes: {
        class:
          "tiptap-content book-md-body focus:outline-none min-h-[min(400px,52vh)] px-1 py-2",
      },
    },
    onUpdate: ({ editor: ed }) => {
      const json = ed.getJSON() as unknown as Record<string, unknown>;
      const md = tiptapDocToMarkdown(json);
      onChange({
        json,
        text: md || ed.getText(),
        characters: ed.storage.characterCount?.characters() ?? ed.getText().length,
      });
    },
  });

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!readOnly && streamingMarkdown === null);
  }, [editor, readOnly, streamingMarkdown]);

  useEffect(() => {
    if (!editor) return;
    const bumpFigureDoc = () => setFigureDocRevision((r) => r + 1);
    editor.on("update", bumpFigureDoc);
    return () => {
      editor.off("update", bumpFigureDoc);
    };
  }, [editor]);

  const getFigureOrdinal = useCallback(
    (figureId: string) => {
      if (!editor || !figureId) return 0;
      let idx = 0;
      let found = 0;
      editor.state.doc.descendants((node) => {
        if (node.type.name !== "figureBlock") return;
        idx += 1;
        if (String(node.attrs.figureId ?? "") === figureId) found = idx;
      });
      return found;
    },
    [editor, figureDocRevision],
  );

  const syncFigureNumbersFromEditor = useCallback((): Promise<void> => {
    if (!editor || !bookId || !chapterIndex) return Promise.resolve();
    return new Promise((resolve) => {
      if (figureRefreshTimerRef.current) clearTimeout(figureRefreshTimerRef.current);
      figureRefreshTimerRef.current = setTimeout(() => {
        figureRefreshTimerRef.current = null;
        void refreshChapterFigures(
          bookId,
          chapterIndex,
          editor.getJSON() as unknown as Record<string, unknown>,
        )
          .then((items) => {
            for (const fig of items) {
              editor.commands.updateFigureBlockAttrs(fig.id, {
                figureNumber: fig.figure_number ?? "",
              });
            }
            setFigureDocRevision((r) => r + 1);
          })
          .catch(() => {})
          .finally(() => resolve());
      }, 400);
    });
  }, [editor, bookId, chapterIndex]);

  useEffect(() => {
    if (!editor) return;
    previewHandlersRef.current = {
      onAccept: () => {
        const preview = aiInlinePreviewKey.getState(editor.state);
        if (!preview) return;
        applyPreviewContent(preview);
        editor.commands.clearAiInlinePreview();
        toast.success("已应用");
      },
      onReject: () => {
        editor.commands.clearAiInlinePreview();
        toast("已取消");
      },
    };
  });

  useEffect(() => {
    if (!editor) return;
    editor.commands.clearAiInlinePreview();
  }, [chapter.id, editor]);

  useEffect(() => {
    figureSyncAttemptRef.current = null;
    figureSyncInFlightRef.current = false;
    formatRecoveredChapterRef.current = null;
  }, [chapter.id]);

  /** 从 DB 恢复：text 仍是 Markdown，但 tiptap_json 曾被 sync 压成纯段落 */
  useEffect(() => {
    if (!editor || readOnly) return;
    const c = chapter.content as Record<string, unknown> | null | undefined;
    const text = typeof c?.text === "string" ? c.text : "";
    const tj = c?.tiptap_json;
    if (!text.trim() || !tj || typeof tj !== "object") return;
    const tjRecord = tj as Record<string, unknown>;
    const incomplete = tiptapMissingMarkdownFeatures(text, tjRecord);
    if (!incomplete && tiptapHasRichStructure(tjRecord)) return;
    if (!incomplete && tiptapHasFigureBlocks(tjRecord)) return;
    if (!isRichMarkdown(text)) return;
    if (formatRecoveredChapterRef.current === chapter.id) return;
    formatRecoveredChapterRef.current = chapter.id;
    const figBlocks = extractFigureBlocksFromDoc(tj as Record<string, unknown>);
    const rich = buildTiptapDocWithFigures(text, figBlocks);
    safeSetContent(migrateTiptapDoc(rich));
  }, [chapter.id, chapter.content, editor, readOnly]);

  useEffect(() => {
    if (!bookId || !chapterIndex || readOnly || !editor) return;
    const c = chapter.content as Record<string, unknown> | null | undefined;
    const text = typeof c?.text === "string" ? c.text : "";
    const hasAnnotation = ANNOTATION_TEST_RE.test(text);
    if (!hasAnnotation) return;

    const editorJson = JSON.stringify(editor.getJSON());
    if (editorJson.includes('"figureBlock"')) return;

    const tjStr = JSON.stringify(c?.tiptap_json ?? {});
    if (tjStr.includes('"figureBlock"')) return;

    const syncKey = `${chapter.id}:${text.length}`;
    if (figureSyncAttemptRef.current === syncKey || figureSyncInFlightRef.current) return;
    figureSyncAttemptRef.current = syncKey;
    figureSyncInFlightRef.current = true;

    void syncChapterFigures(bookId, chapterIndex)
      .then((doc) => {
        const rich = enrichSyncedTiptapDoc(text, doc);
        safeSetContent(migrateTiptapDoc(rich));
      })
      .catch(() => {
        figureSyncAttemptRef.current = null;
      })
      .finally(() => {
        figureSyncInFlightRef.current = false;
      });
  }, [bookId, chapterIndex, chapter.id, chapter.content, editor, readOnly]);

  useEffect(() => {
    if (!bookId || !chapterIndex || !editor || readOnly) return;
    const tj = (chapter.content as Record<string, unknown> | null | undefined)?.tiptap_json;
    if (!tj || !JSON.stringify(tj).includes('"figureBlock"')) return;
    void refreshChapterFigures(
      bookId,
      chapterIndex,
      editor.getJSON() as unknown as Record<string, unknown>,
    )
      .then((items) => {
        for (const fig of items) {
          editor.commands.updateFigureBlockAttrs(fig.id, {
            figureNumber: fig.figure_number ?? "",
            fileUrl: fig.file_url ?? "",
            status: fig.status as FigureStatus,
            caption: fig.caption ?? "",
            figureType: fig.figure_type as FigureType,
            fileVersion: figureFileVersion(fig.updated_at, Date.now()),
          });
        }
        setFigureDocRevision((r) => r + 1);
      })
      .catch(() => {});
  }, [bookId, chapterIndex, chapter.id, editor, readOnly]);

  useEffect(() => {
    if (!editor || !onSelectionChange) return;
    const emit = () => {
      const { from, to, empty } = editor.state.selection;
      onSelectionChange(empty ? "" : editor.state.doc.textBetween(from, to, "\n"));
    };
    emit();
    editor.on("selectionUpdate", emit);
    return () => {
      editor.off("selectionUpdate", emit);
    };
  }, [editor, onSelectionChange]);

  useImperativeHandle(
    ref,
    () => ({
      appendText: (t: string) => {
        if (!editor || !t) return;
        const { state, view } = editor;
        const tr = state.tr;
        const endSel = TextSelection.atEnd(state.doc);
        tr.setSelection(endSel);
        tr.insertText(t);
        tr.setMeta("addToHistory", false);
        view.dispatch(tr);
      },
      clear: () => {
        if (!editor) return;
        editor.commands.clearContent(true);
      },
      applyPlainMarkdown: (raw: string) => {
        if (!editor) return;
        const normalized = normalizeGfmMarkdown(raw);
        if (!normalized.trim()) return;
        if (isRichMarkdown(normalized)) {
          try {
            safeSetContent(markdownToTiptapDoc(normalized));
            return;
          } catch {
            /* fall through */
          }
        }
        if (shouldParseAsMarkdown(normalized)) {
          safeSetContent(plainTextMarkdownToTiptapDoc(normalized));
        } else {
          safeSetContent(normalized);
        }
      },
      applyServerContent: (content) => {
        if (!editor) return;
        safeSetContent(resolveChapterEditorContent(content));
      },
      scrollToSectionAnchor: (anchorId) => {
        if (!editor || !anchorId) return false;
        let anchorPos: number | null = null;
        editor.state.doc.descendants((node, pos) => {
          if (anchorPos != null) return false;
          if (node.type.name === "heading" && node.attrs.id === anchorId) {
            anchorPos = pos;
            return false;
          }
          return true;
        });
        if (anchorPos == null) return false;
        const el = editor.view.dom.querySelector(`#${CSS.escape(anchorId)}`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        editor.chain().focus().setTextSelection(anchorPos + 1).run();
        return true;
      },
      getSerialized: () => {
        if (!editor) return null;
        return {
          json: editor.getJSON() as unknown as Record<string, unknown>,
          text: editor.getText(),
        };
      },
      insertReferenceQuote: (body: string, filename: string) => {
        if (!editor || !body.trim()) return;
        editor
          .chain()
          .focus()
          .insertContent({
            type: "blockquote",
            content: [
              { type: "paragraph", content: [{ type: "text", text: body.trim() }] },
              {
                type: "paragraph",
                content: [{ type: "text", text: `—— ${filename}`, marks: [{ type: "italic" }] }],
              },
            ],
          })
          .run();
      },
      insertCitationMarks: (marks: string[]) => {
        if (!editor || !marks.length) return;
        const text = marks.join(" ") + " ";
        editor.chain().focus().insertContent(text).run();
      },
      insertLiteratureQuotes: (quotes) => {
        if (!editor || !quotes.length) return;
        const blocks = quotes
          .filter((q) => q.quote_body?.trim())
          .map((q) => ({
            type: "paragraph" as const,
            content: [{ type: "text" as const, text: q.quote_body.trim() }],
          }));
        if (!blocks.length) return;
        editor.chain().focus().insertContent(blocks).insertContent({ type: "paragraph" }).run();
      },
      replaceQuoteWithSuggestion: (quote: string, suggestion: string) => {
        if (!editor || !quote.trim() || !suggestion.trim()) return false;
        const sug = cleanSuggestionText(suggestion);
        if (!sug) return false;
        const q = quote.trim();
        const { from, to, empty } = editor.state.selection;
        const selected = empty ? "" : editor.state.doc.textBetween(from, to, "\n");
        if (normalizeMatchText(selected) === normalizeMatchText(q)) {
          editor.chain().focus().deleteRange({ from, to }).insertContent(sug).run();
          return true;
        }
        const range = resolveQuoteRange(q);
        if (range && range.from < range.to) {
          editor.chain().focus().deleteRange(range).insertContentAt(range.from, sug).run();
          return true;
        }
        return false;
      },
      getSelectionPlain: () => {
        if (!editor) return "";
        const { from, to, empty } = editor.state.selection;
        return empty ? "" : editor.state.doc.textBetween(from, to, "\n");
      },
      getChapterContextAroundSelection: (maxChars?: number) => getChapterContextAroundSelection(maxChars),
      showAiPreview: (payload: EditorAiPreviewPayload) => showInlinePreview(payload),
      confirmAiPreview: () => {
        if (!editor) return false;
        const preview = aiInlinePreviewKey.getState(editor.state);
        if (!preview) return false;
        const ok = applyPreviewContent(preview);
        if (ok) editor.commands.clearAiInlinePreview();
        return ok;
      },
      dismissAiPreview: () => {
        editor?.commands.clearAiInlinePreview();
      },
      hasAiPreview: () => {
        if (!editor) return false;
        return aiInlinePreviewKey.getState(editor.state) != null;
      },
      focusEditor: () => {
        editor?.chain().focus().run();
      },
      applySyncedDoc: (doc: Record<string, unknown>, markdownText?: string) => {
        if (!editor) return;
        const c = chapter.content as Record<string, unknown> | null | undefined;
        const text =
          markdownText ?? (typeof c?.text === "string" ? c.text : "");
        try {
          const rich = text.trim() ? enrichSyncedTiptapDoc(text, doc) : doc;
          safeSetContent(migrateTiptapDoc(rich));
        } catch (e) {
          console.warn("[applySyncedDoc] failed, keeping current editor content", e);
        }
      },
      updateFigureBlock: (figureId: string, patch: Record<string, unknown>) => {
        editor?.commands.updateFigureBlockAttrs(figureId, patch);
      },
      insertFigureBlock: (attrs: Record<string, unknown>) => {
        editor?.commands.insertFigureBlock(attrs);
      },
      applyFigureResult: (fig, options) => {
        if (!editor) return;
        const nextVersion = Date.now();
        const patch = {
          figureId: fig.figure_id,
          fileUrl: fig.file_url ?? "",
          figureNumber: fig.figure_number ?? "",
          status: fig.status as FigureStatus,
          caption: fig.caption ?? "",
          figureType: fig.figure_type as FigureType,
          fileVersion: nextVersion,
        };
        const targetId = options?.targetFigureId || fig.figure_id;
        let updated = false;

        const tryUpdate = (matchId: string) => {
          let hit = false;
          editor.state.doc.descendants((node, pos) => {
            if (hit || node.type.name !== "figureBlock") return;
            if (String(node.attrs.figureId ?? "") !== matchId) return;
            editor.view.dispatch(
              editor.state.tr.setNodeMarkup(pos, undefined, { ...node.attrs, ...patch }),
            );
            hit = true;
            updated = true;
          });
          return hit;
        };

        if (targetId) tryUpdate(targetId);

        if (!updated) {
          editor.state.doc.descendants((node, pos) => {
            if (updated || node.type.name !== "figureBlock") return;
            const id = String(node.attrs.figureId ?? "");
            if (id) return;
            editor.view.dispatch(
              editor.state.tr.setNodeMarkup(pos, undefined, { ...node.attrs, ...patch }),
            );
            updated = true;
          });
        }

        if (!updated && !options?.replaceOnly) {
          editor.commands.insertFigureBlock(patch);
        } else if (!updated) {
          toast.error("未在正文中找到对应图表块，请先在正文中引用该图");
          return;
        }

        void syncFigureNumbersFromEditor();
      },
    }),
    [editor, syncFigureNumbersFromEditor, chapter.content],
  );

  async function runAi(mode: SelectionEditMode) {
    if (!editor || readOnly) return;
    const { from, to, empty } = editor.state.selection;
    if (empty) {
      toast.error("请先选中一段文字");
      return;
    }
    const selected = editor.state.doc.textBetween(from, to, "\n");
    if (!selected.trim()) {
      toast.error("所选内容为空");
      return;
    }
    setAiBusy(mode);
    try {
      const { text } = await editChapterSelection(bookId, chapterIndex, {
        mode,
        text: selected,
        context: getChapterContextAroundSelection(),
      });
      showInlinePreview({ quote: selected, suggestion: text.trim(), kind: "replace" });
      toast.success("已在正文原位置显示预览");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "AI 处理失败");
    } finally {
      setAiBusy(null);
    }
  }

  const bubbleShouldShow = useCallback(
    (props: {
      editor: Editor;
      element: HTMLElement;
      view: EditorView;
      state: EditorState;
      from: number;
      to: number;
    }) => {
      if (bubbleGateRef.current.readOnly || bubbleGateRef.current.stream) return false;
      const { editor: ed, element, view, state, from, to } = props;
      const { doc, selection } = state;
      const { empty } = selection;
      const isEmptyTextBlock = !doc.textBetween(from, to).length && isTextSelection(selection);
      const isChildOfMenu = element.contains(document.activeElement);
      const hasEditorFocus = view.hasFocus() || isChildOfMenu;
      if (!hasEditorFocus || empty || isEmptyTextBlock || !ed.isEditable) return false;
      return true;
    },
    [],
  );

  const showStreamPreview = readOnly && streamingMarkdown !== null;

  const figureContextValue = useMemo(
    () => ({
      bookId,
      chapterIndex,
      editor: editor ?? null,
      figureDocRevision,
      getFigureOrdinal,
      refreshFigureNumbers: syncFigureNumbersFromEditor,
      onFigureUpdated: (figureId: string, patch: Record<string, unknown>) => {
        editor?.commands.updateFigureBlockAttrs(figureId, patch);
      },
      onQuoteFigure: onQuoteFigure,
    }),
    [
      bookId,
      chapterIndex,
      editor,
      figureDocRevision,
      getFigureOrdinal,
      syncFigureNumbersFromEditor,
      onQuoteFigure,
    ],
  );

  if (!editor) {
    return <div className="text-sm text-slate-500">编辑器加载中…</div>;
  }

  function applyHeadingLevel(level: 0 | 1 | 2 | 3) {
    if (!editor || readOnly) return;
    const { from, to, empty } = editor.state.selection;
    if (level === 0) {
      if (!empty) {
        const text = editor.state.doc.textBetween(from, to, "\n");
        editor
          .chain()
          .focus()
          .deleteRange({ from, to })
          .insertContentAt(from, { type: "paragraph", content: text ? [{ type: "text", text }] : [] })
          .run();
      } else {
        editor.chain().focus().setParagraph().run();
      }
      setHeadingMenuOpen(false);
      return;
    }
    if (!empty) {
      const text = editor.state.doc.textBetween(from, to, "\n");
      editor
        .chain()
        .focus()
        .deleteRange({ from, to })
        .insertContentAt(from, {
          type: "heading",
          attrs: { level },
          content: text ? [{ type: "text", text }] : [],
        })
        .run();
    } else {
      editor.chain().focus().toggleHeading({ level }).run();
    }
    setHeadingMenuOpen(false);
  }

  return (
    <EditorErrorBoundary key={chapter.id ? `ch-${chapter.id}` : `idx-${chapter.index}`}>
      <FigureBlockContext.Provider value={figureContextValue}>
      <div className="flex min-h-0 flex-1 flex-col border-0 bg-transparent p-0 pt-1 shadow-none">
      {!showStreamPreview ? (
        <>
          <BubbleMenu
            editor={editor}
            shouldShow={bubbleShouldShow}
            tippyOptions={{ duration: 120 }}
            className="tiptap-bubble flex flex-wrap gap-1 rounded-lg border border-slate-200 bg-white px-1 py-1 shadow-md"
          >
            <button
              type="button"
              className={`rounded px-2 py-1 text-xs font-semibold ${editor.isActive("bold") ? "bg-violet-100 text-violet-800" : "text-slate-700"}`}
              onClick={() => editor.chain().focus().toggleBold().run()}
              title="加粗"
            >
              <Bold className="h-4 w-4" />
            </button>
            <div className="relative">
              <button
                type="button"
                className={`rounded px-2 py-1 text-xs font-semibold ${editor.isActive("heading") ? "bg-violet-100 text-violet-800" : "text-slate-700"}`}
                title="标题"
                onClick={() => setHeadingMenuOpen((v) => !v)}
              >
                H
              </button>
              {headingMenuOpen ? (
                <>
                  <div className="fixed inset-0 z-[150]" aria-hidden onClick={() => setHeadingMenuOpen(false)} />
                  <div className="absolute left-0 top-full z-[160] mt-1 min-w-[10rem] rounded-lg border border-slate-200 bg-white py-1 text-xs shadow-lg">
                    <button type="button" className="block w-full px-3 py-1.5 text-left hover:bg-slate-50" onClick={() => applyHeadingLevel(1)}>
                      H1　章标题
                    </button>
                    <button type="button" className="block w-full px-3 py-1.5 text-left hover:bg-slate-50" onClick={() => applyHeadingLevel(2)}>
                      H2　节标题
                    </button>
                    <button type="button" className="block w-full px-3 py-1.5 text-left hover:bg-slate-50" onClick={() => applyHeadingLevel(3)}>
                      H3　小节标题
                    </button>
                    <button type="button" className="block w-full px-3 py-1.5 text-left hover:bg-slate-50" onClick={() => applyHeadingLevel(0)}>
                      ¶　正文
                    </button>
                  </div>
                </>
              ) : null}
            </div>
            <span className="mx-0.5 w-px self-stretch bg-slate-200" />
            <button
              type="button"
              disabled={readOnly || aiBusy !== null}
              className="rounded px-2 py-1 text-xs font-medium text-slate-700 hover:bg-violet-50 disabled:opacity-50"
              title="AI 润色"
              onClick={() => void runAi("polish")}
            >
              {aiBusy === "polish" ? <Loader2 className="h-4 w-4 animate-spin" /> : "润色"}
            </button>
            <button
              type="button"
              disabled={readOnly || aiBusy !== null}
              className="rounded px-2 py-1 text-xs font-medium text-slate-700 hover:bg-violet-50 disabled:opacity-50"
              title="AI 扩写"
              onClick={() => void runAi("expand")}
            >
              {aiBusy === "expand" ? <Loader2 className="h-4 w-4 animate-spin" /> : "扩写"}
            </button>
            <button
              type="button"
              disabled={readOnly || aiBusy !== null}
              className="rounded px-2 py-1 text-xs font-medium text-slate-700 hover:bg-violet-50 disabled:opacity-50"
              title="AI 缩写"
              onClick={() => void runAi("shrink")}
            >
              {aiBusy === "shrink" ? <Loader2 className="h-4 w-4 animate-spin" /> : "缩写"}
            </button>
            <button
              type="button"
              disabled={readOnly || aiBusy !== null}
              className="rounded px-2 py-1 text-xs font-medium text-violet-800 hover:bg-violet-50 disabled:opacity-50"
              title="AI 降重"
              onClick={() => void runAi("dedupe")}
            >
              {aiBusy === "dedupe" ? <Loader2 className="h-4 w-4 animate-spin" /> : "降重"}
            </button>
            <button
              type="button"
              disabled={readOnly}
              className="rounded px-2 py-1 text-xs font-medium text-slate-700 hover:bg-violet-50 disabled:opacity-50"
              title="AI 助手"
              onClick={() => {
                const { from, to, empty } = editor.state.selection;
                const selected = empty ? "" : editor.state.doc.textBetween(from, to, "\n");
                onOpenAssistantPanel?.(selected);
              }}
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </BubbleMenu>
          <EditorContent editor={editor} />
        </>
      ) : (
        <div className="chapter-md-preview book-md-body prose prose-slate max-w-none px-1 py-2 prose-headings:font-semibold">
          <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
            {streamingMarkdown}
          </ReactMarkdown>
        </div>
      )}
      </div>
      </FigureBlockContext.Provider>
    </EditorErrorBoundary>
  );
});

export default ChapterTiptapEditor;
