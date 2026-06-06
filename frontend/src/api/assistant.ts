import { client } from "@/api/client";

export type AssistantIntent =
  | "polish"
  | "rewrite"
  | "expand"
  | "condense"
  | "style_adjust"
  | "term_check"
  | "gen_flowchart"
  | "gen_chart"
  | "gen_figure"
  | "regen_figure";

export type AssistantRequest = {
  user_text?: string;
  selected_text?: string;
  figure_id?: string;
  cursor_paragraph?: string;
  explicit_intent?: AssistantIntent;
  chart_type?: string;
  sub_kind?: string;
};

export type AssistantTextResponse = {
  type: "text";
  content: string;
  intent?: string;
};

export type AssistantFigureResponse = {
  type: "figure";
  figure_id: string;
  file_url: string | null;
  svg_url?: string | null;
  figure_number: string | null;
  status: string;
  caption: string | null;
  figure_type: string;
  updated_at?: string | null;
  intent?: string;
};

export type AssistantConfirmResponse = {
  type: "confirm";
  message: string;
  intent?: string;
  confidence?: number;
  candidates?: string[];
};

export type AssistantResponse =
  | AssistantTextResponse
  | AssistantFigureResponse
  | AssistantConfirmResponse;

export async function callAssistant(
  bookId: string,
  chapterIndex: number,
  body: AssistantRequest,
): Promise<AssistantResponse> {
  const { data } = await client.post<AssistantResponse>(
    `/books/${bookId}/chapters/${chapterIndex}/assistant`,
    body,
    { timeout: 180000 },
  );
  return data;
}
