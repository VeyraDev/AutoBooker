/** 图表占位标注（支持多行内容） */

export const ANNOTATION_INNER_RE =
  /(?:FLOWCHART|CHART|FIGURE|DIAGRAM|SCREENSHOT):\s*[\s\S]*?(?=\])/;

export const ANNOTATION_FULL_RE =
  /\[(?:FLOWCHART|CHART|FIGURE|DIAGRAM|SCREENSHOT):\s*[\s\S]*?\]/g;

export const ANNOTATION_TEST_RE =
  /\[(?:FLOWCHART|CHART|FIGURE|DIAGRAM|SCREENSHOT):/i;

export const FIGURE_CAPTION_LINE_RE = /^图\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]\s*(.+)$/;

export const TABLE_CAPTION_LINE_RE = /^表\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]\s*(.+)$/;

export function extractAnnotationsFromMarkdown(text: string): string[] {
  return text.match(ANNOTATION_FULL_RE) ?? [];
}
