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
import { textHasMathDelimiters, tiptapDocHasMathNodes, tiptapDocHasRawMathText } from "@/lib/migrateMathInTiptapDoc";
import { isRichMarkdown, markdownToTiptapDoc } from "@/lib/markdownToTiptapDoc";
import { tiptapDocCollapsedButTextStructured } from "@/lib/reconcileTablesFromText";
import { plainTextMarkdownToTiptapDoc, shouldParseAsMarkdown } from "@/lib/plainTextMarkdownToTiptap";

/** 生成结束 / 从服务端载入时：优先保留 tiptap_json 结构，仅就地修补公式/表格。 */
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
  const needsMathMigration =
    tjObj != null &&
    (tiptapDocHasRawMathText(tjObj) ||
      (text.trim() && textHasMathDelimiters(text) && !tiptapDocHasMathNodes(tjObj)));
  const collapsedWall =
    Boolean(tjObj && text.trim() && tiptapDocCollapsedButTextStructured(text, tjObj));

  const needsFigureRebuild =
    textHasAnnotations && (!tjHasFigures || tjFigureCount < annotationCount);

  if (
    tjObj &&
    !needsFigureRebuild &&
    !tiptapIncomplete &&
    !needsMathMigration &&
    !collapsedWall &&
    (tjHasFigures || tjRich)
  ) {
    return migrateTiptapDoc(tjObj, { sourceText: text });
  }

  if (text.trim()) {
    const figBlocks = tjObj ? extractFigureBlocksFromDoc(tjObj) : [];

    if (needsFigureRebuild || tiptapIncomplete || needsMathMigration || collapsedWall) {
      if (tjObj && tiptapDocHasRawMathText(tjObj) && !collapsedWall && !tiptapIncomplete) {
        return migrateTiptapDoc(tjObj, { sourceText: text });
      }
      return migrateTiptapDoc(buildTiptapDocWithFigures(text, figBlocks), { sourceText: text });
    }

    if (isRichMarkdown(text) && (!tjObj || !tjRich)) {
      try {
        return migrateTiptapDoc(markdownToTiptapDoc(text), { sourceText: text });
      } catch {
        /* fall through */
      }
    }

    if (shouldParseAsMarkdown(text)) {
      return migrateTiptapDoc(plainTextMarkdownToTiptapDoc(text), { sourceText: text });
    }
  }

  if (tjObj) {
    return migrateTiptapDoc(tjObj, { sourceText: text });
  }

  if (text.trim()) {
    return {
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "text", text: text.trim() }] }],
    };
  }
  return { type: "doc", content: [{ type: "paragraph" }] };
}
