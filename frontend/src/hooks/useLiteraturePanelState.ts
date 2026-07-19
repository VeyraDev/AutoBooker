import { useCallback, useEffect, useRef } from "react";

import type { LiteraturePaper, LiteratureTab } from "@/types/literature";

export type LiteraturePanelPersisted = {
  query: string;
  tab: LiteratureTab;
  tabbed: Record<LiteratureTab, LiteraturePaper[]>;
  refinedQueries: string[];
  sourceHint: string;
  selectedKeys: string[];
  items?: LiteraturePaper[];
};

function storageKey(bookId: string, mode: string) {
  return `autobooker:literature:${bookId}:${mode}`;
}

export function loadLiteraturePanelState(
  bookId: string,
  mode: string,
): LiteraturePanelPersisted | null {
  try {
    const raw = sessionStorage.getItem(storageKey(bookId, mode));
    if (!raw) return null;
    return JSON.parse(raw) as LiteraturePanelPersisted;
  } catch {
    return null;
  }
}

export function saveLiteraturePanelState(
  bookId: string,
  mode: string,
  state: LiteraturePanelPersisted,
) {
  try {
    sessionStorage.setItem(storageKey(bookId, mode), JSON.stringify(state));
  } catch {
    /* quota */
  }
}

/** 切换侧栏 Tab 时保留文献检索状态；卸载时中止进行中的请求 */
export function useLiteratureSearchAbort() {
  const abortRef = useRef<AbortController | null>(null);

  const begin = useCallback(() => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    return ac.signal;
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  return { begin, abort };
}
