import katex from "katex";

/**
 * LaTeX 源码规范化：剥离 Markdown/TeX 分隔符，提取编号与 label，供编辑与导出共用。
 * 原则：数据库存纯 LaTeX 表达式，不含 $、$$、\\[\\] 等包裹符。
 */

export type LatexKind = "inline" | "block";

export type NormalizedLatex = {
  latex: string;
  kind: LatexKind;
  numbered: boolean;
  equationNumber: string;
  label: string;
  /** 是否从输入中自动识别为独立公式 */
  autoDetectedBlock: boolean;
  stripped: string[];
};

function trim(s: string): string {
  return s.replace(/^\s+|\s+$/g, "");
}

/** 行内公式中不应保留硬换行（常见于 LLM/JSON 在 $N 与 (i)$ 之间插入 \n）。 */
export function normalizeInlineLatexWhitespace(latex: string): string {
  return latex.replace(/\s*\n+\s*/g, "");
}

function stripTagAndLabel(src: string): {
  latex: string;
  numbered: boolean;
  equationNumber: string;
  label: string;
  stripped: string[];
} {
  let latex = src;
  let numbered = false;
  let equationNumber = "";
  let label = "";
  const stripped: string[] = [];

  const labelRe = /\\label\s*\{([^{}]+)\}/g;
  let lm: RegExpExecArray | null;
  while ((lm = labelRe.exec(latex)) !== null) {
    label = lm[1].trim();
    stripped.push("\\label{…}");
  }
  latex = latex.replace(/\\label\s*\{[^{}]+\}/g, "").trim();

  const tagMatch = latex.match(/\\tag\s*\{([^{}]+)\}\s*$/);
  if (tagMatch) {
    numbered = true;
    equationNumber = tagMatch[1].trim();
    latex = latex.replace(/\\tag\s*\{[^{}]+\}\s*$/, "").trim();
    stripped.push("\\tag{…}");
  }

  return { latex, numbered, equationNumber, label, stripped };
}

/** 从用户输入或粘贴内容解析出可存储的 LaTeX 本体。 */
export function normalizeLatexInput(
  raw: string,
  opts?: { preferKind?: LatexKind; keepExistingNumber?: { numbered?: boolean; equationNumber?: string; label?: string } },
): NormalizedLatex {
  let s = raw.replace(/\r\n/g, "\n");
  const stripped: string[] = [];
  let kind: LatexKind = opts?.preferKind ?? "inline";
  let autoDetectedBlock = false;

  const blockDouble = /^\s*\$\$([\s\S]*?)\$\$\s*$/;
  const blockBracket = /^\s*\\\[([\s\S]*?)\\\]\s*$/;
  const inlineParen = /^\s*\\\(([\s\S]*?)\\\)\s*$/;
  const inlineSingle = /^\s*(?<!\$)\$(?!\$)([\s\S]*?)(?<!\$)\$(?!\$)\s*$/;

  const dm = s.match(blockDouble);
  if (dm) {
    s = dm[1];
    kind = "block";
    autoDetectedBlock = true;
    stripped.push("$$…$$");
  } else {
    const bm = s.match(blockBracket);
    if (bm) {
      s = bm[1];
      kind = "block";
      autoDetectedBlock = true;
      stripped.push("\\[…\\]");
    } else {
      const im = s.match(inlineParen);
      if (im) {
        s = im[1];
        kind = "inline";
        stripped.push("\\(…\\)");
      } else {
        const sm = s.match(inlineSingle);
        if (sm) {
          s = sm[1];
          kind = "inline";
          stripped.push("$…$");
        }
      }
    }
  }

  if (!autoDetectedBlock && opts?.preferKind === "block" && !s.match(/^\s*[\$\[\\]/)) {
    kind = "block";
  }

  const meta = stripTagAndLabel(trim(s));
  stripped.push(...meta.stripped);

  const keep = opts?.keepExistingNumber;
  const numbered = meta.numbered || Boolean(keep?.numbered);
  const equationNumber = meta.equationNumber || String(keep?.equationNumber ?? "").trim();
  const label = meta.label || String(keep?.label ?? "").trim();
  const latexBody = kind === "inline" ? normalizeInlineLatexWhitespace(meta.latex) : meta.latex;

  return {
    latex: latexBody,
    kind,
    numbered,
    equationNumber,
    label,
    autoDetectedBlock,
    stripped,
  };
}

export type KatexRenderResult = {
  html: string;
  error: string | null;
};

/** KaTeX 预览/NodeView 渲染；displayMode 与行内/独立公式一致。 */
export function renderLatexToHtml(latex: string, displayMode: boolean): KatexRenderResult {
  const src = latex.trim();
  if (!src) return { html: "", error: null };
  try {
    const html = katex.renderToString(src, {
      displayMode,
      throwOnError: true,
      strict: "ignore",
      trust: false,
    });
    return { html, error: null };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    try {
      const fallback = katex.renderToString(src, {
        displayMode,
        throwOnError: false,
        strict: "ignore",
      });
      return { html: fallback, error: msg };
    } catch {
      return { html: `<span class="katex-error">${escapeHtml(msg)}</span>`, error: msg };
    }
  }
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** 粘贴文本是否「几乎全是」一条公式（可转为 math 节点而非纯文本）。 */
export function pastedTextLooksLikeMath(raw: string): boolean {
  const t = raw.trim();
  if (!t) return false;
  if (/^\$\$[\s\S]+\$\$$/.test(t)) return true;
  if (/^\\\[[\s\S]+\\\]$/.test(t)) return true;
  if (/^\\\([\s\S]+\\\)$/.test(t)) return true;
  if (/^(?<!\$)\$(?!\$)[\s\S]+(?<!\$)\$(?!\$)$/.test(t)) return true;
  return false;
}

/** 插入片段：`{cursor}` 表示插入后选中该位置。 */
export type LatexSnippet = { label: string; latex: string; title?: string };

export const LATEX_SNIPPET_GROUPS: { title: string; items: LatexSnippet[] }[] = [
  {
    title: "结构",
    items: [
      { label: "分数", latex: "\\frac{{cursor}a}{b}", title: "分数 \\frac{a}{b}" },
      { label: "根号", latex: "\\sqrt{{cursor}x}", title: "平方根" },
      { label: "n次根", latex: "\\sqrt[n]{{cursor}x}", title: "n 次根" },
      { label: "上标", latex: "x^{{cursor}n}", title: "上标" },
      { label: "下标", latex: "x_{{cursor}i}", title: "下标" },
      { label: "括号", latex: "\\left({cursor}\\right)", title: "自适应括号" },
    ],
  },
  {
    title: "运算",
    items: [
      { label: "求和", latex: "\\sum_{{cursor}i=1}^{n}", title: "求和" },
      { label: "积分", latex: "\\int_{{cursor}a}^{b}", title: "定积分" },
      { label: "极限", latex: "\\lim_{{cursor}x \\to 0}", title: "极限" },
      { label: "偏导", latex: "\\frac{\\partial {cursor}f}{\\partial x}", title: "偏导数" },
      { label: "向量", latex: "\\vec{{cursor}v}", title: "向量" },
    ],
  },
  {
    title: "关系",
    items: [
      { label: "±", latex: "\\pm ", title: "正负" },
      { label: "×", latex: "\\times ", title: "乘号" },
      { label: "÷", latex: "\\div ", title: "除号" },
      { label: "≤", latex: "\\leq ", title: "小于等于" },
      { label: "≥", latex: "\\geq ", title: "大于等于" },
      { label: "≠", latex: "\\neq ", title: "不等于" },
      { label: "≈", latex: "\\approx ", title: "约等于" },
      { label: "→", latex: "\\rightarrow ", title: "箭头" },
      { label: "⇌", latex: "\\rightleftharpoons ", title: "可逆反应" },
    ],
  },
  {
    title: "希腊",
    items: [
      { label: "α", latex: "\\alpha " },
      { label: "β", latex: "\\beta " },
      { label: "γ", latex: "\\gamma " },
      { label: "δ", latex: "\\delta " },
      { label: "θ", latex: "\\theta " },
      { label: "λ", latex: "\\lambda " },
      { label: "μ", latex: "\\mu " },
      { label: "π", latex: "\\pi " },
      { label: "σ", latex: "\\sigma " },
      { label: "ω", latex: "\\omega " },
      { label: "Δ", latex: "\\Delta " },
      { label: "Σ", latex: "\\Sigma " },
      { label: "Ω", latex: "\\Omega " },
    ],
  },
  {
    title: "文本",
    items: [
      { label: "text", latex: "\\text{{cursor}{}}", title: "正体文本（化学式等）" },
      { label: "mathrm", latex: "\\mathrm{{cursor}{}}", title: "罗马体" },
    ],
  },
];

export function applySnippetAtCursor(
  current: string,
  selectionStart: number,
  selectionEnd: number,
  snippet: string,
): { value: string; selectionStart: number; selectionEnd: number } {
  const cursorToken = "{cursor}";
  const idx = snippet.indexOf(cursorToken);
  const insert = idx >= 0 ? snippet.replace(cursorToken, "") : snippet;
  const before = current.slice(0, selectionStart);
  const after = current.slice(selectionEnd);
  const value = before + insert + after;
  if (idx >= 0) {
    const pos = before.length + idx;
    return { value, selectionStart: pos, selectionEnd: pos };
  }
  const pos = before.length + insert.length;
  return { value, selectionStart: pos, selectionEnd: pos };
}
