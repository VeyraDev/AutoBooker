import { useQuery } from "@tanstack/react-query";
import { client } from "@/api/client";

const jsonHeaders = { "Content-Type": "application/json" } as const;

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

export async function completeProjectStart(bookId: string) {
  const { data } = await client.post(`/books/${bookId}/project-start/complete`, {}, { headers: jsonHeaders });
  return data;
}

export async function bootstrapProjectStart(
  bookId: string,
  payload: { creation_origin?: CreationOrigin; raw_goal_text?: string; negative_constraints_text?: string } = {},
) {
  const { data } = await client.post(`/books/${bookId}/project-start/bootstrap`, payload, { headers: jsonHeaders });
  return data as { intake_id: string; status: string; writing_basis_id: string };
}

export async function fetchIntake(bookId: string) {
  const { data } = await client.get<IntakeResponse>(`/books/${bookId}/intake`);
  return data;
}

export function useIntake(bookId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["intake", bookId],
    queryFn: () => fetchIntake(bookId),
    enabled: !!bookId && (options?.enabled ?? true),
  });
}
