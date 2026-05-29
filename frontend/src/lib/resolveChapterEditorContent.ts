import {
  buildTiptapDocWithFigures,
  countAnnotationsInMarkdown,
  extractFigureBlocksFromDoc,
  tiptapHasFigureBlocks,
  tiptapHasRichStructure,
  tiptapMissingMarkdownFeatures,
} from "@/lib/buildTiptapDocWithFigures";
import { ANNOTATION_TEST_RE } from "@/lib/annotationPatterns";
import { migrateTiptapDoc } from "@/lib/migrateTiptapDoc";
import { isRichMarkdown, markdownToTiptapDoc } from "@/lib/markdownToTiptapDoc";
import { plainTextMarkdownToTiptapDoc, shouldParseAsMarkdown } from "@/lib/plainTextMarkdownToTiptap";

/** 生成结束 / 从服务端载入时：优先用 Markdown 原文恢复排版，并嵌入图表占位。 */
export function resolveChapterEditorContent(
  content: Record<string, unknown> | null | undefined,
): Record<string, unknown> {
  const c = content ?? {};
  const text = typeof c.text === "string" ? c.text : "";
  const tjObj =
    c.tiptap_json && typeof c.tiptap_json === "object"
      ? (c.tiptap_json as Record<string, unknown>)
      : null;

  const textHasAnnotations = text.trim() ? ANNOTATION_TEST_RE.test(text) : false;
  const annotationCount = textHasAnnotations ? countAnnotationsInMarkdown(text) : 0;
  const tjRich = tjObj ? tiptapHasRichStructure(tjObj) : false;
  const tjHasFigures = tjObj ? tiptapHasFigureBlocks(tjObj) : false;
  const tjFigureCount = tjObj ? extractFigureBlocksFromDoc(tjObj).length : 0;
  const tiptapIncomplete =
    tjObj && text.trim() ? tiptapMissingMarkdownFeatures(text, tjObj) : false;

  const needsFigureRebuild =
    textHasAnnotations && (!tjHasFigures || tjFigureCount < annotationCount);

  if (tjObj && !needsFigureRebuild && !tiptapIncomplete && (tjHasFigures || tjRich)) {
    return migrateTiptapDoc(tjObj);
  }

  if (text.trim()) {
    const figBlocks = tjObj ? extractFigureBlocksFromDoc(tjObj) : [];

    if (textHasAnnotations || figBlocks.length > 0 || tiptapIncomplete) {
      return migrateTiptapDoc(buildTiptapDocWithFigures(text, figBlocks));
    }

    if (isRichMarkdown(text) && (!tjObj || !tjRich)) {
      try {
        return migrateTiptapDoc(markdownToTiptapDoc(text));
      } catch {
        /* fall through */
      }
    }

    if (shouldParseAsMarkdown(text)) {
      return migrateTiptapDoc(plainTextMarkdownToTiptapDoc(text));
    }
  }

  if (tjObj) {
    return migrateTiptapDoc(tjObj);
  }

  if (text.trim()) {
    return {
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "text", text: text.trim() }] }],
    };
  }
  return { type: "doc", content: [{ type: "paragraph" }] };
}
