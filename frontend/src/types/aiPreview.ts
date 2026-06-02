import type { SelectionEditMode } from "@/api/chapters";

export type AiPreviewKind = "replace" | "insert";

export type EditorAiPreviewPayload = {
  quote: string;
  suggestion: string;
  kind: AiPreviewKind;
  label?: string;
  char_offset?: number | null;
  paragraph_index?: number | null;
};

export type AiAssistantMode = SelectionEditMode | "flowchart" | "rewrite";
