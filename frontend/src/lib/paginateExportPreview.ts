/**
 * 按开本切成真实书页：
 * - 「章过渡页」独占整页；每一节（h2）另起一页
 * - 段落按字切分填满当页
 * - 正文页底绝对定位页码（不被 overflow 裁掉）
 * - 目录用 table 强制页码右对齐
 */

export type PaginateOptions = {
  widthMm: number;
  heightMm: number;
};

const FOOTER_H = 28;

function createSheet(opts: {
  kind: string;
  pageNum: number | null;
  showArabic: boolean;
  special?: "flyleaf";
}): HTMLElement {
  const sheet = document.createElement("section");
  sheet.className = `export-page export-sheet export-sheet--${opts.kind}${
    opts.special === "flyleaf" ? " export-sheet--flyleaf" : ""
  }`;
  sheet.dataset.section = opts.kind;
  if (opts.pageNum != null) sheet.dataset.page = String(opts.pageNum);

  const inner = document.createElement("div");
  inner.className = "sheet-inner";
  sheet.appendChild(inner);

  const footer = document.createElement("div");
  footer.className = "sheet-footer";
  // 正文页必须有可见页码；空格占位避免高度塌缩（最终用绝对定位）
  if (opts.showArabic && opts.pageNum != null) {
    footer.textContent = String(opts.pageNum);
  } else {
    footer.innerHTML = "&nbsp;";
  }
  sheet.appendChild(footer);

  return sheet;
}

function ensureSheetHeight(sheet: HTMLElement, widthMm: number, heightMm: number): void {
  let w = sheet.getBoundingClientRect().width || sheet.offsetWidth;
  if (w < 40) {
    const parentW = sheet.parentElement?.getBoundingClientRect().width || 0;
    w = Math.min(parentW > 40 ? parentW : 420, 420);
    sheet.style.width = `${w}px`;
  }
  const h = (w * heightMm) / widthMm;
  sheet.style.width = `${w}px`;
  sheet.style.height = `${h}px`;
  sheet.style.maxHeight = `${h}px`;
  sheet.style.minHeight = `${h}px`;
  sheet.style.aspectRatio = "auto";
}

function overflows(inner: HTMLElement): boolean {
  void inner.offsetHeight;
  const ch = inner.clientHeight;
  if (ch < 8) return false;
  return inner.scrollHeight > ch + 1;
}

function isChapterFlyleaf(node: Node): boolean {
  return (
    node instanceof HTMLElement &&
    node.classList.contains("flyleaf-block") &&
    node.getAttribute("data-flyleaf") === "chapter"
  );
}

function isSectionHeading(node: Node): boolean {
  return node instanceof HTMLElement && node.tagName === "H2";
}

/** 把目录行打成两列表：标题底边点线拉满，页码右对齐 */
function forceTocRowTable(el: HTMLElement): HTMLElement {
  if (el.tagName === "TABLE" && el.classList.contains("toc-row")) {
    // 旧三列中间 leader：压成两列
    const cells = el.querySelectorAll("td");
    if (cells.length === 3) {
      const title = (cells[0].textContent || "").trim();
      const page = (cells[2].textContent || "").trim();
      const level2 = el.classList.contains("toc-level-2");
      return buildTocTable(title, page, level2);
    }
    return el;
  }

  const titleEl = el.querySelector(".toc-title");
  const pageEl = el.querySelector(".toc-page");
  const title = titleEl ? (titleEl.textContent || "").trim() : (el.textContent || "").trim();
  const page = (pageEl?.textContent || "").trim();
  const level2 = el.classList.contains("toc-level-2");
  return buildTocTable(title, page, level2);
}

function buildTocTable(title: string, page: string, level2: boolean): HTMLElement {
  const table = document.createElement("table");
  table.className = `toc-row${level2 ? " toc-level-2" : ""}`;
  table.setAttribute(
    "style",
    "width:100%;table-layout:fixed;border-collapse:collapse;margin:6px 0;",
  );
  const colgroup = document.createElement("colgroup");
  colgroup.innerHTML = `<col/><col style="width:2.2em"/>`;
  table.appendChild(colgroup);

  const tr = document.createElement("tr");
  const tdTitle = document.createElement("td");
  tdTitle.className = "toc-title";
  tdTitle.textContent = title;
  tdTitle.setAttribute(
    "style",
    `padding:0 8px 2px ${level2 ? "1.5em" : "0"};vertical-align:bottom;font-size:10.5pt;border-bottom:1px dotted #666;`,
  );

  const tdPage = document.createElement("td");
  tdPage.className = "toc-page";
  tdPage.textContent = page;
  tdPage.setAttribute(
    "style",
    "width:2.2em;white-space:nowrap;text-align:right;vertical-align:bottom;font-size:10.5pt;font-variant-numeric:tabular-nums;padding:0 0 2px 0;",
  );

  tr.appendChild(tdTitle);
  tr.appendChild(tdPage);
  table.appendChild(tr);
  return table;
}

function expandFlowNodes(nodes: Node[]): Node[] {
  const out: Node[] = [];
  for (const n of nodes) {
    if (!(n instanceof HTMLElement)) {
      if (n.nodeType === Node.TEXT_NODE && (n.textContent || "").trim()) out.push(n);
      continue;
    }
    if (n.classList.contains("flyleaf-block") && n.getAttribute("data-flyleaf") === "section") {
      const h2 = document.createElement("h2");
      h2.textContent = n.textContent || "";
      out.push(h2);
      continue;
    }
    if (n.classList.contains("toc-note")) continue;
    if (n.classList.contains("toc-list")) {
      for (const child of Array.from(n.children)) {
        if (child instanceof HTMLElement && child.classList.contains("toc-row")) {
          out.push(forceTocRowTable(child));
        } else if (child instanceof HTMLElement && child.classList.contains("toc-line")) {
          // 后端已输出「标题+点线+页码」单行，直接分页
          out.push(child);
        } else if (child.nodeType === Node.ELEMENT_NODE) {
          out.push(child);
        }
      }
      continue;
    }
    if (n.classList.contains("toc-row")) {
      out.push(forceTocRowTable(n));
      continue;
    }
    if (n.classList.contains("toc-line")) {
      out.push(n);
      continue;
    }
    out.push(n);
  }
  return out;
}

function isTextSplittable(el: HTMLElement): boolean {
  const tag = el.tagName;
  if (el.classList.contains("toc-line")) return false;
  if (tag === "P" || tag === "BLOCKQUOTE" || tag === "LI") return true;
  if (tag === "TABLE" || el.classList.contains("toc-row")) return false;
  if (tag === "H1" || tag === "H2" || tag === "H3" || tag === "H4") return false;
  if (tag === "PRE" || tag === "IMG") return false;
  if (el.children.length === 0 && (el.textContent || "").length > 0) return true;
  return false;
}

function cloneEmptyShell(el: HTMLElement): HTMLElement {
  const c = el.cloneNode(false) as HTMLElement;
  c.removeAttribute("id");
  return c;
}

function maxFittingChars(inner: HTMLElement, el: HTMLElement, fullText: string): number {
  if (!fullText) return 0;
  let lo = 0;
  let hi = fullText.length;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    const probe = cloneEmptyShell(el);
    probe.textContent = fullText.slice(0, mid);
    inner.appendChild(probe);
    const over = overflows(inner);
    inner.removeChild(probe);
    if (over) hi = mid - 1;
    else lo = mid;
  }
  return lo;
}

function preferBreakPoint(text: string, at: number): number {
  if (at <= 0 || at >= text.length) return at;
  const window = Math.min(12, at);
  const slice = text.slice(at - window, at);
  const marks = "，。；：、！？…—）》」』";
  for (let i = slice.length - 1; i >= 0; i--) {
    if (marks.includes(slice[i]!)) return at - window + i + 1;
  }
  return at;
}

function placeNode(inner: HTMLElement, node: Node): Node | null {
  if (!(node instanceof HTMLElement)) {
    inner.appendChild(node);
    if (!overflows(inner)) return null;
    inner.removeChild(node);
    return node;
  }

  if (isChapterFlyleaf(node)) {
    inner.appendChild(node);
    return null;
  }

  if (!isTextSplittable(node)) {
    inner.appendChild(node);
    if (!overflows(inner)) return null;
    inner.removeChild(node);
    return node;
  }

  const fullText = node.textContent || "";
  if (!fullText.trim()) {
    inner.appendChild(node);
    return null;
  }

  inner.appendChild(node);
  if (!overflows(inner)) return null;
  inner.removeChild(node);

  let fit = maxFittingChars(inner, node, fullText);
  if (fit <= 0) return node;

  fit = preferBreakPoint(fullText, fit);
  if (fit <= 0) fit = maxFittingChars(inner, node, fullText);
  if (fit <= 0) return node;

  const head = cloneEmptyShell(node);
  head.textContent = fullText.slice(0, fit);
  inner.appendChild(head);

  if (fit >= fullText.length) return null;

  const rest = cloneEmptyShell(node);
  rest.textContent = fullText.slice(fit);
  if (rest.tagName === "P") {
    rest.style.textIndent = "0";
    rest.classList.add("para-continue");
  }
  return rest;
}

function paginateFlowSection(
  section: HTMLElement,
  args: {
    kind: string;
    showArabic: boolean;
    pageCounter: { n: number };
    widthMm: number;
    heightMm: number;
  },
): void {
  const { kind, showArabic, pageCounter, widthMm, heightMm } = args;
  const raw = Array.from(section.childNodes).filter((n) => {
    if (n.nodeType === Node.TEXT_NODE) return (n.textContent || "").trim().length > 0;
    return n.nodeType === Node.ELEMENT_NODE;
  });
  const queue = expandFlowNodes(raw);

  const parent = section.parentElement;
  if (!parent) return;

  const sheets: HTMLElement[] = [];

  const startSheet = (special?: "flyleaf") => {
    const sheet = createSheet({
      kind,
      pageNum: showArabic ? pageCounter.n : null,
      showArabic,
      special,
    });
    parent.insertBefore(sheet, section);
    sheets.push(sheet);
    ensureSheetHeight(sheet, widthMm, heightMm);
    void sheet.offsetHeight;

    const sheetInner = sheet.querySelector(".sheet-inner") as HTMLElement;
    // 绝对定位：内容区底边留出页脚，页码永远看得见
    sheetInner.style.position = "absolute";
    sheetInner.style.top = "0";
    sheetInner.style.left = "0";
    sheetInner.style.right = "0";
    sheetInner.style.bottom = `${FOOTER_H}px`;
    sheetInner.style.height = "auto";
    sheetInner.style.maxHeight = "none";
    sheetInner.style.overflow = "hidden";
    sheetInner.style.boxSizing = "border-box";
    sheetInner.style.padding = "18px 20px 4px";

    const footer = sheet.querySelector(".sheet-footer") as HTMLElement;
    footer.style.position = "absolute";
    footer.style.left = "0";
    footer.style.right = "0";
    footer.style.bottom = "0";
    footer.style.height = `${FOOTER_H}px`;
    footer.style.lineHeight = `${FOOTER_H}px`;
    footer.style.textAlign = "center";
    footer.style.fontSize = "10.5pt";
    footer.style.color = "#222";
    footer.style.zIndex = "3";
    footer.style.pointerEvents = "none";

    void sheetInner.offsetHeight;
    return sheetInner;
  };

  let inner = startSheet();

  const bumpPage = () => {
    if (showArabic) pageCounter.n += 1;
  };

  const newPage = (special?: "flyleaf") => {
    bumpPage();
    inner = startSheet(special);
  };

  let safety = 0;
  const SAFETY = 20000;

  while (queue.length > 0 && safety < SAFETY) {
    safety += 1;
    const node = queue.shift()!;

    if (isChapterFlyleaf(node)) {
      if (inner.childNodes.length > 0) newPage("flyleaf");
      else sheets[sheets.length - 1].classList.add("export-sheet--flyleaf");
      inner.appendChild(node);
      newPage();
      continue;
    }

    if (isSectionHeading(node) && inner.childNodes.length > 0) {
      newPage();
    }

    const remainder = placeNode(inner, node);
    if (remainder == null) continue;

    if (inner.childNodes.length === 0) {
      if (remainder instanceof HTMLElement && isTextSplittable(remainder)) {
        const text = remainder.textContent || "";
        const fit = maxFittingChars(inner, remainder, text);
        if (fit > 0 && fit < text.length) {
          const head = cloneEmptyShell(remainder);
          head.textContent = text.slice(0, fit);
          inner.appendChild(head);
          const rest = cloneEmptyShell(remainder);
          rest.textContent = text.slice(fit);
          if (rest.tagName === "P") {
            rest.style.textIndent = "0";
            rest.classList.add("para-continue");
          }
          queue.unshift(rest);
          newPage();
          continue;
        }
      }
      inner.appendChild(remainder instanceof Node ? remainder : node);
      newPage();
      continue;
    }

    queue.unshift(remainder);
    newPage();
  }

  while (sheets.length > 1) {
    const last = sheets[sheets.length - 1];
    const lastInner = last.querySelector(".sheet-inner");
    if (lastInner && lastInner.childNodes.length === 0) {
      last.remove();
      sheets.pop();
      if (showArabic) pageCounter.n -= 1;
    } else break;
  }

  if (showArabic && sheets.length > 0) {
    pageCounter.n += 1;
  }

  section.remove();
}

export function paginateExportPreview(root: HTMLElement, opts: PaginateOptions): void {
  if (!root) return;

  // contentEditable 会破坏分页布局：关闭后再排版
  root.contentEditable = "false";
  root.querySelectorAll("[contenteditable]").forEach((el) => {
    (el as HTMLElement).contentEditable = "false";
  });

  let style = root.querySelector("style[data-paginate-style]") as HTMLStyleElement | null;
  if (!style) {
    style = document.createElement("style");
    style.dataset.paginateStyle = "1";
    root.prepend(style);
  }
  style.textContent = `
.export-preview-root { gap: 28px; padding-bottom: 40px; }
.export-sheet {
  width: min(100%, 420px);
  display: block;
  padding: 0 !important;
  overflow: hidden !important;
  position: relative !important;
  box-sizing: border-box;
  background: #fff;
}
.export-sheet .sheet-inner {
  overflow: hidden;
  box-sizing: border-box;
}
.export-sheet .sheet-footer {
  font-family: "宋体","SimSun",serif;
  font-variant-numeric: tabular-nums;
}
.export-sheet--flyleaf .sheet-inner {
  display: flex;
  align-items: center;
  justify-content: center;
}
.export-preview-root p.para-continue { text-indent: 0 !important; }
.export-toc, .export-preface, .export-chapter, .export-bibliography {
  aspect-ratio: auto !important;
  height: auto !important;
  min-height: 0 !important;
  overflow: visible !important;
}
.page-label { display: none !important; }
table.toc-row { width: 100% !important; table-layout: fixed !important; border-collapse: collapse !important; }
table.toc-row td.toc-title { border-bottom: 1px dotted #666 !important; }
table.toc-row td.toc-page { text-align: right !important; white-space: nowrap !important; }
`;

  root.querySelectorAll(".page-label").forEach((el) => el.remove());

  const pageCounter = { n: 1 };
  const flow = Array.from(
    root.querySelectorAll<HTMLElement>(
      ":scope > .export-toc, :scope > .export-preface, :scope > .export-chapter, :scope > .export-bibliography",
    ),
  );

  for (const section of flow) {
    const kind = section.dataset.section || "chapter";
    const showArabic = kind === "chapter" || kind === "bibliography";
    paginateFlowSection(section, {
      kind,
      showArabic,
      pageCounter,
      widthMm: opts.widthMm,
      heightMm: opts.heightMm,
    });
  }

  // 排版后再允许局部字段编辑（不碰分页结构）
  root.querySelectorAll<HTMLElement>("[data-field]").forEach((el) => {
    el.contentEditable = "true";
  });
}
