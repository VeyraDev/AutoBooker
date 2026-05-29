import { client } from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

export type PrefaceData = {
  enabled: boolean;
  target_words: number;
  brief: string;
  summary: string;
  text?: string;
  status: string;
  word_count: number;
  tiptap_json?: Record<string, unknown> | null;
};

export async function getPreface(bookId: string): Promise<PrefaceData> {
  const { data } = await client.get<PrefaceData>(`/books/${bookId}/preface`);
  return data;
}

export async function putPreface(bookId: string, patch: Partial<PrefaceData>): Promise<PrefaceData> {
  const { data } = await client.put<PrefaceData>(`/books/${bookId}/preface`, patch);
  return data;
}

/** 与章节生成流一致：使用 authStore 中的 Bearer token */
export async function openPrefaceGenerateStream(bookId: string): Promise<Response> {
  const token = useAuthStore.getState().accessToken;
  const base = import.meta.env.VITE_API_BASE ?? "";
  const res = await fetch(`${base}/books/${bookId}/preface/generate`, {
    method: "POST",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      Accept: "text/event-stream",
    },
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const raw = await res.text();
      const j = JSON.parse(raw) as { detail?: string };
      if (typeof j.detail === "string") msg = j.detail;
      else if (raw.trim()) msg = raw.slice(0, 200);
    } catch {
      /* ignore */
    }
    throw new Error(res.status === 401 ? "请先登录后再生成前言" : msg || "前言生成请求失败");
  }
  if (!res.body) throw new Error("前言生成响应无正文流");
  return res;
}

