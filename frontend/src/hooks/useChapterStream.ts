import { useCallback, useEffect, useRef } from "react";

import { useAuthStore } from "@/stores/authStore";

export function isCitationInsufficientError(err: Error): boolean {
  return err.message.includes("引用库不足");
}

function parseGenerateError(status: number, body: string): Error {
  const trimmed = body.trim();
  if (!trimmed) return new Error(`HTTP ${status}`);
  try {
    const parsed = JSON.parse(trimmed) as { detail?: unknown };
    const detail = parsed.detail;
    if (typeof detail === "string" && detail.trim()) return new Error(detail.trim());
    if (Array.isArray(detail)) {
      const msg = detail
        .map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg: unknown }).msg) : String(x)))
        .join("；");
      if (msg.trim()) return new Error(msg.trim());
    }
  } catch {
    /* not JSON */
  }
  return new Error(trimmed.length > 500 ? `${trimmed.slice(0, 500)}…` : trimmed);
}

async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onEvent: (obj: Record<string, unknown>) => void,
): Promise<boolean> {
  const decoder = new TextDecoder();
  let buffer = "";
  let sawDone = false;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            const obj = JSON.parse(line.slice(6)) as Record<string, unknown>;
            if (obj.done === true) sawDone = true;
            onEvent(obj);
          } catch {
            /* ignore malformed line */
          }
        }
      }
    }
  }
  return sawDone;
}

async function openGenerateStream(
  bookId: string,
  chapterIndex: number,
  signal: AbortSignal,
  forceGenerate = false,
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  const token = useAuthStore.getState().accessToken;
  const base = import.meta.env.VITE_API_BASE ?? "";
  const qs = forceGenerate ? "?force_generate=true" : "";
  const res = await fetch(`${base}/books/${bookId}/chapters/${chapterIndex}/generate${qs}`, {
    method: "POST",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      Accept: "text/event-stream",
    },
    signal,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw parseGenerateError(res.status, text);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("响应无正文流");
  return reader;
}

export type ChapterStreamCallbacks = {
  onToken: (token: string) => void;
  onDone: (payload?: { markdown?: string; truncated?: boolean }) => void;
  onError: (err: Error) => void;
  /** 请求被中止（例如切换章节） */
  onAbort?: () => void;
};

export type ChapterStreamStartOptions = {
  /** 跳过引用库数量校验（后端 force_generate） */
  forceGenerate?: boolean;
};

export function useChapterStream() {
  const abortRef = useRef<AbortController | null>(null);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const start = useCallback(
    async (
      bookId: string,
      chapterIndex: number,
      cb: ChapterStreamCallbacks,
      opts?: ChapterStreamStartOptions,
    ) => {
      abort();
      const ac = new AbortController();
      abortRef.current = ac;
      try {
        const reader = await openGenerateStream(
          bookId,
          chapterIndex,
          ac.signal,
          Boolean(opts?.forceGenerate),
        );
        let errored = false;
        const sawDone = await parseSSEStream(reader, (obj) => {
          if ("error" in obj && obj.error != null) {
            errored = true;
            const code = String(obj.error);
            if (code === "narrative_failed") {
              const detail = typeof obj.detail === "string" ? obj.detail.trim() : "";
              cb.onError(new Error(detail || "全书叙事宪法生成失败，请检查网络或模型配置后重试"));
              return;
            }
            cb.onError(new Error(code));
            return;
          }
          if (typeof obj.token === "string") cb.onToken(obj.token);
          if (obj.done === true) {
            const markdown = typeof obj.markdown === "string" ? obj.markdown : undefined;
            const truncated = obj.truncated === true;
            cb.onDone(
              markdown !== undefined || truncated
                ? { ...(markdown !== undefined ? { markdown } : {}), ...(truncated ? { truncated } : {}) }
                : undefined,
            );
          }
        });
        if (!errored && !sawDone && !ac.signal.aborted) {
          cb.onError(new Error("连接已结束但未收到完成标记，请刷新或重试本章"));
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") {
          cb.onAbort?.();
          return;
        }
        cb.onError(e instanceof Error ? e : new Error(String(e)));
      }
    },
    [abort],
  );

  useEffect(() => () => abort(), [abort]);

  return { start, abort };
}
