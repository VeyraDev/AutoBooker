import { client } from "@/api/client";

export type ProjectMemory = {
  id: string;
  book_id: string;
  memory_type: string;
  content: string;
  source_turn_id?: string | null;
  strength: string;
  confirmed: boolean;
  created_at: string;
  updated_at: string;
};

export type ProjectMemoryPatch = {
  content?: string;
  memory_type?: string;
  strength?: string;
  confirmed?: boolean;
};

export async function listMemories(bookId: string) {
  const { data } = await client.get<ProjectMemory[]>(`/books/${bookId}/memories`);
  return data;
}

export async function patchMemory(bookId: string, memoryId: string, patch: ProjectMemoryPatch) {
  const { data } = await client.patch<ProjectMemory>(`/books/${bookId}/memories/${memoryId}`, patch);
  return data;
}

export async function deleteMemory(bookId: string, memoryId: string) {
  await client.delete(`/books/${bookId}/memories/${memoryId}`);
}

export const MEMORY_TYPE_LABELS: Record<string, string> = {
  fact: "项目事实",
  decision: "已做决策",
  constraint: "约束禁令",
  open_question: "待确认问题",
  risk: "风险提醒",
};

export const STRENGTH_LABELS: Record<string, string> = {
  must: "必须",
  should: "应当",
  preference: "偏好",
};
