import { mathSegmentsToPlaceholderHtml, tokenizeMathInMarkdown } from "@/lib/mathTokenizer";

/**
 * 将 Markdown 中的 LaTeX 分隔符转为仅含 data-latex 的占位 HTML。
 * 不嵌入 KaTeX DOM——数据库只存 LaTeX，KaTeX 仅在编辑区 NodeView 中渲染。
 */
export function mathMarkdownToHtml(markdown: string): string {
  const segments = tokenizeMathInMarkdown(markdown);
  return mathSegmentsToPlaceholderHtml(segments);
}
