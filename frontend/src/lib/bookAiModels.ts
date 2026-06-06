import { normalizeAiModelValue, type LlmModelsResponse } from "@/api/config";
import type { AiScene } from "@/stores/aiModelPrefsStore";
import type { Book } from "@/types/book";

const SCENE_FIELD: Record<AiScene, keyof Book> = {
  outline: "outline_ai_model",
  constitution: "constitution_ai_model",
  writing: "writing_ai_model",
};

export function effectiveSceneModel(
  scene: AiScene,
  opts: {
    book?: Book | null;
    prefs?: Partial<Record<AiScene, string | null>>;
    catalog?: LlmModelsResponse;
  },
): string {
  const fallback = opts.catalog?.default ?? "deepseek:deepseek-chat";
  const bookField = opts.book?.[SCENE_FIELD[scene]] as string | null | undefined;
  const raw = String(bookField ?? opts.prefs?.[scene] ?? opts.book?.ai_model ?? "").trim();
  if (!raw) return fallback;
  return normalizeAiModelValue(raw, opts.catalog);
}
