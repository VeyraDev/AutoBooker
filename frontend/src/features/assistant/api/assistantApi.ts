import { client } from "@/api/client";

export type WritingBasis = {
  id: string;
  book_id: string;
  version: number;
  status: string;
  direction?: string | null;
  book_promise?: string | null;
  target_readers?: string | null;
  reader_outcome?: string | null;
  scope?: string | null;
  depth?: string | null;
  voice?: string | null;
  material_policy?: string[];
  outline_policy?: string[];
  citation_policy?: string[];
  figure_policy?: string[];
  must_keep?: string[];
  must_avoid?: string[];
  open_questions?: string[];
};

export type AssistantTrace = {
  id: string;
  turn_id: string;
  claim: string;
  evidence?: string[] | null;
  reason_summary?: string | null;
  confidence?: number | null;
};

export type SourceSegment = {
  id: string;
  source_id: string;
  segment_type: string;
  summary: string;
  locator?: string | null;
  confidence: number;
  suggested_usage?: string | null;
  excerpt?: string | null;
  user_confirmed?: boolean | null;
  needs_confirm?: boolean;
};

export type SourceItem = {
  id: string;
  title: string;
  type: string;
  status: string;
  summary?: string | null;
  detected_roles?: string[];
  segments?: SourceSegment[];
};

export type TurnListItem = {
  id: string;
  user_message: string;
  assistant_message: string;
  created_at: string;
};

export type SettingOrigin = {
  origin: string;
  updated_at?: string | null;
};

export type OutlineRoute = {
  mode: string;
  source_id?: string | null;
  reason?: string;
  confidence?: number | null;
  needs_confirmation?: boolean;
  candidate_source_ids?: string[];
};

export type ExtractedRequirement = {
  category?: string;
  content: string;
  strength?: string;
  source_id?: string | null;
};

export type TurnResponse = {
  turn_id: string;
  assistant_message: string;
  writing_basis?: WritingBasis | null;
  book_settings?: Record<string, unknown>;
  setting_origins?: Record<string, SettingOrigin>;
  setting_decisions?: Record<string, unknown>[];
  extracted_requirements?: ExtractedRequirement[];
  confirmed_requirements?: ExtractedRequirement[];
  file_judgements?: Record<string, unknown>[];
  outline_route?: OutlineRoute | null;
  clarification?: Record<string, unknown>;
  search_result?: Record<string, unknown> | null;
  quick_fill_operation_id?: string | null;
  traces?: AssistantTrace[];
  sources?: SourceItem[];
  open_questions?: string[];
  memories?: import("@/features/memory/memoryApi").ProjectMemory[];
  tool_results?: ToolResult[];
  pending_confirmations?: ConfirmationPreview[];
};

export type OutlineReadiness = {
  missing: string[];
  outline_route?: OutlineRoute | null;
  ready: boolean;
};

export type ToolResult = {
  name: string;
  ok: boolean;
  panel_hint: string;
  data: Record<string, unknown>;
  requires_confirmation?: boolean;
  error?: string | null;
};

export type ConfirmationPreview = {
  name: string;
  panel_hint: string;
  data: Record<string, unknown>;
};

export async function sendTurn(
  bookId: string,
  message: string,
  chapterIndex?: number | null,
  assistantMode: "normal" | "quick_fill" = "normal",
) {
  const { data } = await client.post<TurnResponse>(
    `/books/${bookId}/project-assistant/turns`,
    {
      message: message ?? "",
      chapter_index: chapterIndex ?? undefined,
      assistant_mode: assistantMode,
    },
    { timeout: 180_000 },
  );
  return data;
}

export async function undoQuickFill(bookId: string, operationId?: string | null) {
  const { data } = await client.post<{
    operation_id?: string;
    restored?: Record<string, unknown>;
    book_settings?: Record<string, unknown>;
    setting_origins?: Record<string, SettingOrigin>;
  }>(`/books/${bookId}/project-assistant/quick-fill/undo`, {
    operation_id: operationId ?? undefined,
  });
  return data;
}

export async function getOutlineReadiness(bookId: string) {
  const { data } = await client.get<OutlineReadiness>(
    `/books/${bookId}/project-assistant/outline-readiness`,
  );
  return data;
}

export async function listTurns(bookId: string, page = 1) {
  const { data } = await client.get<TurnListItem[]>(`/books/${bookId}/project-assistant/turns`, { params: { page } });
  return data;
}

export async function listTraces(bookId: string, turnId?: string) {
  const { data } = await client.get<AssistantTrace[]>(`/books/${bookId}/project-assistant/traces`, {
    params: turnId ? { turn_id: turnId } : undefined,
  });
  return data;
}

export async function getWritingBasis(bookId: string) {
  const { data } = await client.get<WritingBasis>(`/books/${bookId}/writing-basis`);
  return data;
}

export async function patchWritingBasis(bookId: string, patch: Partial<WritingBasis>) {
  const { data } = await client.patch<WritingBasis>(`/books/${bookId}/writing-basis`, patch);
  return data;
}

export async function confirmWritingBasis(bookId: string) {
  const { data } = await client.post<{ basis_id: string; status: string }>(`/books/${bookId}/writing-basis/confirm`);
  return data;
}

export async function listSources(bookId: string) {
  const { data } = await client.get<SourceItem[]>(`/books/${bookId}/sources`);
  return data;
}

export async function pasteSource(bookId: string, text: string) {
  const { data } = await client.post<SourceItem>(`/books/${bookId}/sources`, { text });
  return data;
}

export async function uploadSource(bookId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<SourceItem>(`/books/${bookId}/sources/upload`, form, {
    timeout: 120_000,
  });
  return data;
}

export async function deleteSource(bookId: string, sourceId: string) {
  await client.delete(`/books/${bookId}/sources/${sourceId}`);
}

export async function readSource(bookId: string, sourceId: string) {
  const { data } = await client.post<SourceItem>(`/books/${bookId}/sources/${sourceId}/read`);
  return data;
}

export async function confirmSourceSegment(bookId: string, segmentId: string, confirmed: boolean) {
  const { data } = await client.post<SourceSegment>(`/books/${bookId}/sources/segments/${segmentId}/confirm`, {
    confirmed,
  });
  return data;
}
