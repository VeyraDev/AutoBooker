import { useCallback, useRef } from "react";

const STORAGE_PREFIX = "autobooker_daily_chars_";

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

/** 按自然日累计本地编辑字数增量（用于今日码字标签与列表统计）。 */
export function useDailyWordDelta(bookId: string | undefined) {
  const prevCharsRef = useRef<number | null>(null);

  const recordChars = useCallback(
    (characters: number) => {
      if (!bookId) return;
      const prev = prevCharsRef.current;
      prevCharsRef.current = characters;
      if (prev === null || characters <= prev) return;
      const delta = characters - prev;
      const key = `${STORAGE_PREFIX}${todayKey()}`;
      try {
        const raw = window.localStorage.getItem(key);
        const map = raw ? (JSON.parse(raw) as Record<string, number>) : {};
        map[bookId] = (map[bookId] ?? 0) + delta;
        window.localStorage.setItem(key, JSON.stringify(map));
      } catch {
        /* ignore quota */
      }
    },
    [bookId],
  );

  return { recordChars };
}

export function getTodayWordsForBook(bookId: string): number {
  const key = `${STORAGE_PREFIX}${todayKey()}`;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return 0;
    const map = JSON.parse(raw) as Record<string, number>;
    return map[bookId] ?? 0;
  } catch {
    return 0;
  }
}

export function getTodayWordsTotal(): number {
  const key = `${STORAGE_PREFIX}${todayKey()}`;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return 0;
    const map = JSON.parse(raw) as Record<string, number>;
    return Object.values(map).reduce((a, b) => a + b, 0);
  } catch {
    return 0;
  }
}
