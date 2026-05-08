import { BubbleMenu, EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import CharacterCount from "@tiptap/extension-character-count";
import { Bold, Italic, Loader2 } from "lucide-react";
import { forwardRef, useEffect, useImperativeHandle, useMemo, useState } from "react";
import toast from "react-hot-toast";

import { TextSelection } from "@tiptap/pm/state";

import { editChapterSelection, type SelectionEditMode } from "@/api/chapters";
import {
  plainTextMarkdownToTiptapDoc,
  shouldParseAsMarkdown,
} from "@/lib/plainTextMarkdownToTiptap";
import type { Chapter } from "@/types/chapter";

export type ChapterEditorHandle = {
  appendText: (t: string) => void;
  clear: () => void;
  applyPlainMarkdown: (raw: string) => void;
  getSerialized: () => { json: Record<string, unknown>; text: string } | null;
};

type Props = {
  chapter: Chapter;
  readOnly: boolean;
  bookId: string;
  chapterIndex: number;
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

const ChapterTiptapEditor = forwardRef<ChapterEditorHandle, Props>(function ChapterTiptapEditor(
  { chapter, readOnly, bookId, chapterIndex, onChange },
  ref,
) {
  const [aiBusy, setAiBusy] = useState<SelectionEditMode | null>(null);

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
      const { text } = await editChapterSelection(bookId, chapterIndex, { mode, text: selected });
      editor.chain().focus().deleteRange({ from, to }).insertContent(text.trim()).run();
      toast.success(mode === "polish" ? "已润色" : mode === "expand" ? "已扩写" : "已缩写");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "AI 处理失败");
    } finally {
      setAiBusy(null);
    }
  }

  if (!editor) {
    return <div className="text-sm text-slate-500">编辑器加载中…</div>;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <BubbleMenu
        editor={editor}
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
        <button
          type="button"
          className={`rounded px-2 py-1 text-xs font-semibold ${editor.isActive("italic") ? "bg-violet-100 text-violet-800" : "text-slate-700"}`}
          onClick={() => editor.chain().focus().toggleItalic().run()}
          title="斜体"
        >
          <Italic className="h-4 w-4" />
        </button>
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
      </BubbleMenu>
      <EditorContent editor={editor} />
      <p className="mt-3 text-right text-[11px] text-slate-400">
        {editor.storage.characterCount?.characters() ?? editor.getText().length} 字
      </p>
    </div>
  );
});

export default ChapterTiptapEditor;
