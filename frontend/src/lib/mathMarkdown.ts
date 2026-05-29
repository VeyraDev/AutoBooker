import katex from "katex";

/** 将 Markdown 中的 $...$ / $$...$$ 转为带 data-latex 的 HTML，供 TipTap generateJSON 解析 */
export function mathMarkdownToHtml(markdown: string): string {
  let out = markdown.replace(/\r\n/g, "\n");

  out = out.replace(/\$\$([\s\S]+?)\$\$/g, (_m, latex: string) => {
    const trimmed = latex.trim();
    const escaped = trimmed.replace(/"/g, "&quot;");
    try {
      const html = katex.renderToString(trimmed, { displayMode: true, throwOnError: false });
      return `<div data-type="math-block" data-latex="${escaped}">${html}</div>`;
    } catch {
      return `<div data-type="math-block" data-latex="${escaped}">${trimmed}</div>`;
    }
  });

  out = out.replace(/(?<!\$)\$(?!\$)([^\$\n]+?)\$(?!\$)/g, (_m, latex: string) => {
    const trimmed = latex.trim();
    const escaped = trimmed.replace(/"/g, "&quot;");
    try {
      const html = katex.renderToString(trimmed, { displayMode: false, throwOnError: false });
      return `<span data-type="math-inline" data-latex="${escaped}">${html}</span>`;
    } catch {
      return `<span data-type="math-inline" data-latex="${escaped}">${trimmed}</span>`;
    }
  });

  return out;
}
