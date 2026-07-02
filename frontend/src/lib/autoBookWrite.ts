const PENDING_AUTO_WRITE_PREFIX = "autobooker_auto_write_";

export function peekPendingAutoWrite(bookId: string): boolean {
  try {
    return sessionStorage.getItem(`${PENDING_AUTO_WRITE_PREFIX}${bookId}`) === "1";
  } catch {
    return false;
  }
}

/** 进度页进入写作页前标记：写作页挂载后自动调用 handleStartWriting('auto') */
export function markPendingAutoWrite(bookId: string): void {
  try {
    sessionStorage.setItem(`${PENDING_AUTO_WRITE_PREFIX}${bookId}`, "1");
  } catch {
    /* ignore */
  }
}

export function consumePendingAutoWrite(bookId: string): boolean {
  try {
    const key = `${PENDING_AUTO_WRITE_PREFIX}${bookId}`;
    if (sessionStorage.getItem(key) === "1") {
      sessionStorage.removeItem(key);
      return true;
    }
  } catch {
    /* ignore */
  }
  return false;
}
