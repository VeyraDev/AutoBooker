import { normalizeAiModelValue, type LlmModelsResponse } from "@/api/config";
import type { UserAiModels } from "@/types/auth";

export type UserAiScene = "outline" | "constitution" | "writing" | "assistant";

const USER_SCENE_FIELD: Record<UserAiScene, keyof UserAiModels> = {
  outline: "outline_ai_model",
  constitution: "constitution_ai_model",
  writing: "writing_ai_model",
  assistant: "assistant_ai_model",
};

/** 系统默认模型（用户未选择时使用） */
export function systemDefaultModel(catalog?: LlmModelsResponse): string {
  return catalog?.default ?? "deepseek:deepseek-chat";
}

export function resolveUserSceneModel(
  scene: UserAiScene,
  userModels: UserAiModels | null | undefined,
  catalog?: LlmModelsResponse,
): string {
  const raw = String(userModels?.[USER_SCENE_FIELD[scene]] ?? "").trim();
  if (!raw) return systemDefaultModel(catalog);
  return normalizeAiModelValue(raw, catalog);
}
