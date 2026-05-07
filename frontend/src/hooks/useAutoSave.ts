import { useCallback, useEffect, useRef, useState } from "react";

type SaveStatus = "idle" | "pending" | "saved" | "error";

export function useAutoSave(debounceMs = 1500) {
  const [status, setStatus] = useState<SaveStatus>("idle");
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancel = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const scheduleSave = useCallback(
    (fn: () => Promise<void>) => {
      cancel();
      setStatus("pending");
      timerRef.current = setTimeout(async () => {
        try {
          await fn();
          setStatus("saved");
          setSavedAt(new Date());
        } catch {
          setStatus("error");
        } finally {
          timerRef.current = null;
        }
      }, debounceMs);
    },
    [cancel, debounceMs],
  );

  useEffect(() => () => cancel(), [cancel]);

  return { status, savedAt, scheduleSave, cancel };
}
