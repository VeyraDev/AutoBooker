/** 去掉审校/AI 建议里常见的「改为：」等前缀，只保留可替换正文。 */
export function cleanSuggestionText(raw: string): string {
  let s = (raw || "").trim();
  s = s.replace(/^(?:改为|建议改为|修改为|建议修改为|修改为：|改为：|建议：)\s*/i, "");
  return s.trim();
}
