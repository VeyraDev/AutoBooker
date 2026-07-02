/** 合并被空行/换行拆开的行内公式，避免 Markdown→TipTap 把 $...$ 单独成段。 */

const INLINE_MATH_ONLY = /^\s*\$(?!\$)(.+?)(?<!\$)\$\s*$/;
const HEADING = /^\s*#{1,6}\s/;
const BLOCK_MATH = /^\s*\$\$/;
const ORPHAN_PUNCT = /^[，。；：、」）\)\]】]/;

export function repairFragmentedInlineMath(markdown: string): string {
  if (!markdown || !markdown.includes("$")) return markdown;

  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const stripped = line.trim();

    if (!stripped) {
      if (
        out.length > 0 &&
        INLINE_MATH_ONLY.test(out[out.length - 1].trim()) &&
        i + 1 < lines.length &&
        lines[i + 1].trim() &&
        !HEADING.test(lines[i + 1]) &&
        !BLOCK_MATH.test(lines[i + 1])
      ) {
        i += 1;
        continue;
      }
      if (
        out.length > 0 &&
        out[out.length - 1].trim() &&
        !INLINE_MATH_ONLY.test(out[out.length - 1].trim()) &&
        i + 1 < lines.length &&
        INLINE_MATH_ONLY.test(lines[i + 1].trim())
      ) {
        i += 1;
        out[out.length - 1] = `${out[out.length - 1].trimEnd()} ${lines[i].trim()}`;
        i += 1;
        continue;
      }
      out.push(line);
      i += 1;
      continue;
    }

    if (BLOCK_MATH.test(stripped) || HEADING.test(stripped)) {
      out.push(line);
      i += 1;
      continue;
    }

    if (INLINE_MATH_ONLY.test(stripped)) {
      if (out.length > 0 && out[out.length - 1].trim() && !INLINE_MATH_ONLY.test(out[out.length - 1].trim())) {
        out[out.length - 1] = `${out[out.length - 1].trimEnd()} ${stripped}`;
      } else if (i + 1 < lines.length && lines[i + 1].trim() && !HEADING.test(lines[i + 1])) {
        const nextStripped = lines[i + 1].trim();
        if (!INLINE_MATH_ONLY.test(nextStripped) && !BLOCK_MATH.test(nextStripped)) {
          out.push(stripped + nextStripped);
          i += 2;
          continue;
        }
        out.push(stripped);
      } else {
        out.push(line);
      }
      i += 1;
      continue;
    }

    if (out.length > 0 && ORPHAN_PUNCT.test(stripped) && out[out.length - 1].trim()) {
      out[out.length - 1] = out[out.length - 1].trimEnd() + stripped;
      i += 1;
      continue;
    }

    out.push(line);
    i += 1;
  }

  return out.join("\n");
}
