import { BubbleMenu, EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import CharacterCount from "@tiptap/extension-character-count";
import { Bold, Heading2, Italic } from "lucide-react";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
} from "react";

import { TextSelection } from "@tiptap/pm/state";

import {
  plainTextMarkdownToTiptapDoc,
  shouldParseAsMarkdown,
} from "@/lib/plainTextMarkdownToTiptap";
import type { Chapter } from "@/types/chapter";

export type ChapterEditorHandle = {
  appendText: (t: string) => void;
  clear: () => void;
  /** 流式结束后用完整原文解析 ### / ** 并替换文档 */
  applyPlainMarkdown: (raw: string) => void;
  /** 立即读取当前编辑器内容（用于流结束后抢先落库，避免 refetch 覆盖） */
  getSerialized: () => { json: Record<string, unknown>; text: string } | null;
};

type Props = {
  chapter: Chapter;
  readOnly: boolean;
  onChange: (payload: { json: Record<string, unknown>; text: string; characters: number }) => void;
};

function initialContent(ch: Chapter): string | Record<string, unknown> {
  const c = ch.content as Record<string, unknown> | null | undefined;
  if (c?.tiptap_json && typeof c.tiptap_json === "object") {
    return c.tiptap_json as Record<string, unknown>;
  }
  const text = typeof c?.text === "string" ? c.text : "";
  if (!text) return "";
  if (shouldParseAsMarkdown(text)) {
    return plainTextMarkdownToTiptapDoc(text);
  }
  return text;
}

function cycleHeading(editor: NonNullable<ReturnType<typeof useEditor>>) {
  if (editor.isActive("heading", { level: 1 })) {
    editor.chain().focus().toggleHeading({ level: 2 }).run();
  } else if (editor.isActive("heading", { level: 2 })) {
    editor.chain().focus().toggleHeading({ level: 3 }).run();
  } else if (editor.isActive("heading", { level: 3 })) {
    editor.chain().focus().setParagraph().run();
  } else {
    editor.chain().focus().toggleHeading({ level: 1 }).run();
  }
}

const ChapterTiptapEditor = forwardRef<ChapterEditorHandle, Props>(function ChapterTiptapEditor(
  { chapter, readOnly, onChange },
  ref,
) {
  const extensions = useMemo(
    () => [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Placeholder.configure({
        placeholder: "从这里开始撰写本章正文…",
      }),
      CharacterCount.configure({ limit: undefined }),
    ],
    [],
  );

  const editor = useEditor({
    extensions,
    editable: !readOnly,
    content: initialContent(chapter),
    editorProps: {
      attributes: {
        class: "tiptap-content focus:outline-none min-h-[min(420px,45vh)] px-1 py-2",
      },
    },
    onUpdate: ({ editor: ed }) => {
      onChange({
        json: ed.getJSON() as unknown as Record<string, unknown>,
        text: ed.getText(),
        characters: ed.storage.characterCount?.characters() ?? ed.getText().length,
      });
    },
  });

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!readOnly);
  }, [editor, readOnly]);

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
        if (!raw.trim()) return;
        if (shouldParseAsMarkdown(raw)) {
          editor.chain().setContent(plainTextMarkdownToTiptapDoc(raw)).run();
        } else {
          editor.chain().setContent(raw).run();
        }
      },
      getSerialized: () => {
        if (!editor) return null;
        return {
          json: editor.getJSON() as unknown as Record<string, unknown>,
          text: editor.getText(),
        };
      },
    }),
    [editor],
  );

  if (!editor) {
    return <div className="text-sm text-slate-500">编辑器加载中…</div>;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <BubbleMenu
        editor={editor}
        tippyOptions={{ duration: 120 }}
        className="tiptap-bubble flex gap-1 rounded-lg border border-slate-200 bg-white px-1 py-1 shadow-md"
      >
          <button
            type="button"
            className={`rounded px-2 py-1 text-xs font-semibold ${editor.isActive("bold") ? "bg-violet-100 text-violet-800" : "text-slate-700"}`}
            onClick={() => editor.chain().focus().toggleBold().run()}
            title="加粗"
          >
            <Bold className="h-4 w-4" />
          </button>
          <button
            type="button"
            className={`rounded px-2 py-1 text-xs font-semibold ${editor.isActive("italic") ? "bg-violet-100 text-violet-800" : "text-slate-700"}`}
            onClick={() => editor.chain().focus().toggleItalic().run()}
            title="斜体"
          >
            <Italic className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="rounded px-2 py-1 text-xs font-semibold text-slate-700"
            onClick={() => cycleHeading(editor)}
            title="标题级别"
          >
            <Heading2 className="h-4 w-4" />
          </button>
      </BubbleMenu>
      <EditorContent editor={editor} />
      <p className="mt-3 text-right text-[11px] text-slate-400">
        {editor.storage.characterCount?.characters() ?? editor.getText().length} 字
      </p>
    </div>
  );
});

export default ChapterTiptapEditor;
