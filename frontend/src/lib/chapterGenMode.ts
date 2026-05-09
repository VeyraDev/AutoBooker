/** 写作页章节生成策略：从策划 Step3 进入时写入 localStorage */

export const chapterGenModeStorageKey = (bookId: string) => `autobooker_chapter_gen_mode_${bookId}`;

export type ChapterGenMode = "auto" | "manual";

export function getChapterGenMode(bookId: string): ChapterGenMode {
  try {
    const v = window.localStorage.getItem(chapterGenModeStorageKey(bookId));
    return v === "manual" ? "manual" : "auto";
  } catch {
    return "auto";
  }
}

export function setChapterGenMode(bookId: string, mode: ChapterGenMode) {
  try {
    window.localStorage.setItem(chapterGenModeStorageKey(bookId), mode);
  } catch {
    /* ignore */
  }
}
