import type { SelectionEditMode } from "@/api/chapters";

export type AiPreviewKind = "replace" | "insert";

export type EditorAiPreviewPayload = {
  quote: string;
  suggestion: string;
  kind: AiPreviewKind;
  label?: string;
  char_offset?: number | null;
  char_start?: number | null;
  char_end?: number | null;
  paragraph_index?: number | null;
  paragraph_id?: string | null;
  locator_confidence?: number | null;
  application_id?: string | null;
  issue_id?: string | null;
  onAccepted?: () => void | Promise<void>;
};

export type AiAssistantMode = SelectionEditMode | "flowchart" | "rewrite";
