import TextAlign from "@tiptap/extension-text-align";
import CharacterCount from "@tiptap/extension-character-count";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import Table from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";
import StarterKit from "@tiptap/starter-kit";

import { MathBlock, MathInline } from "@/lib/tiptap/MathNodes";
import { AiInlinePreview } from "@/lib/tiptap/AiInlinePreview";
import { FigureBlock } from "@/lib/tiptap/FigureBlock";
import { HeadingWithId } from "@/lib/tiptap/HeadingWithId";

/** 与 generateJSON 共用：仅含可序列化进文档的节点，不含 Placeholder / CharacterCount */
export const chapterEditorSchemaExtensions = [
  StarterKit.configure({
    heading: false,
  }),
  HeadingWithId.configure({ levels: [1, 2, 3, 4, 5, 6] }),
  FigureBlock,
  MathInline,
  MathBlock,
  Table.configure({
    resizable: false,
  }),
  TableRow,
  TableHeader,
  TableCell,
  Link.configure({
    openOnClick: false,
    autolink: true,
    linkOnPaste: true,
  }),
  TextAlign.configure({
    types: ["heading", "paragraph"],
    alignments: ["left", "center", "right"],
    defaultAlignment: "left",
  }),
];

export function getChapterEditorExtensions(
  placeholder: string,
  aiPreviewOptions?: { onAccept: () => void; onReject: () => void },
) {
  return [
    ...chapterEditorSchemaExtensions,
    AiInlinePreview.configure(
      aiPreviewOptions ?? { onAccept: () => {}, onReject: () => {} },
    ),
    Placeholder.configure({ placeholder }),
    CharacterCount.configure({ limit: undefined }),
  ];
}
