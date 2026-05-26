import type { SelectionEditMode } from "@/api/chapters";

export type AiPreviewKind = "replace" | "insert";

export type EditorAiPreviewPayload = {
  quote: string;
  suggestion: string;
  kind: AiPreviewKind;
  label?: string;
};

export type AiAssistantMode = SelectionEditMode | "flowchart" | "rewrite";
