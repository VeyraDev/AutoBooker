import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client } from "@/api/client";

export type CreationOrigin = "idea_only" | "material_first" | "outline_first" | "manuscript_continue";

export type IntakeState = {
  id: string;
  creation_origin: CreationOrigin;
  status: string;
  raw_goal_text?: string | null;
  negative_constraints_text?: string | null;
  items: Array<{ id: string; type: string; text?: string | null }>;
  understanding?: {
    id: string;
    version: number;
    user_facing_text?: string | null;
    unclear_questions?: string[] | null;
  } | null;
  writing_plan?: {
    id: string;
    version: number;
    user_facing_text?: string | null;
    status: string;
  } | null;
};

export type IntakeResponse = { intake: IntakeState | null };

export async function initIntake(
  bookId: string,
  payload: { creation_origin: CreationOrigin; raw_goal_text?: string; negative_constraints_text?: string },
) {
  const { data } = await client.post(`/books/${bookId}/intake/init`, payload);
  return data;
}

export async function addIntakeItem(bookId: string, payload: { item_type: string; text_content: string }) {
  const { data } = await client.post(`/books/${bookId}/intake/items`, payload);
  return data;
}

export async function fetchIntake(bookId: string) {
  const { data } = await client.get<IntakeResponse>(`/books/${bookId}/intake`);
  return data;
}

export async function generateUnderstanding(bookId: string) {
  const { data } = await client.post(`/books/${bookId}/intake/understand`);
  return data;
}

export async function patchUnderstanding(bookId: string, correction: string) {
  const { data } = await client.patch(`/books/${bookId}/intake/understanding`, { correction });
  return data;
}

export async function uploadIntakeFile(bookId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post(`/books/${bookId}/intake/items/upload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
export async function confirmUnderstanding(bookId: string) {
  const { data } = await client.post(`/books/${bookId}/intake/confirm`);
  return data;
}

export async function generateWritingPlan(bookId: string) {
  const { data } = await client.post(`/books/${bookId}/writing-plan/generate`);
  return data;
}

export async function patchWritingPlan(bookId: string, userFacingText: string) {
  const { data } = await client.patch(`/books/${bookId}/writing-plan`, { user_facing_text: userFacingText });
  return data;
}

export async function confirmWritingPlan(bookId: string) {
  const { data } = await client.post(`/books/${bookId}/writing-plan/confirm`);
  return data;
}

export function useIntake(bookId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["intake", bookId],
    queryFn: () => fetchIntake(bookId),
    enabled: !!bookId && (options?.enabled ?? true),
  });
}

export function useGenerateUnderstanding(bookId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => generateUnderstanding(bookId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["intake", bookId] }),
  });
}
