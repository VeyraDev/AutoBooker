import { useEffect, useRef, useState } from "react";

/** 将完整文本按字符逐步展示，模拟流式输出。 */
export function useStreamingReveal(
  fullText: string,
  active: boolean,
  options?: { charsPerTick?: number; intervalMs?: number },
) {
  const charsPerTick = options?.charsPerTick ?? 4;
  const intervalMs = options?.intervalMs ?? 18;
  const [visible, setVisible] = useState(active ? "" : fullText);
  const prevFullRef = useRef(fullText);

  useEffect(() => {
    if (!active) {
      setVisible(fullText);
      prevFullRef.current = fullText;
      return;
    }
    if (fullText !== prevFullRef.current) {
      prevFullRef.current = fullText;
      setVisible("");
    }
    if (!fullText) {
      setVisible("");
      return;
    }
    let index = 0;
    setVisible("");
    const timer = window.setInterval(() => {
      index = Math.min(fullText.length, index + charsPerTick);
      setVisible(fullText.slice(0, index));
      if (index >= fullText.length) {
        window.clearInterval(timer);
      }
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [active, fullText, charsPerTick, intervalMs]);

  const done = !active || visible.length >= fullText.length;
  return { visible, done };
}
