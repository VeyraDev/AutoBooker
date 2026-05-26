import { client } from "@/api/client";

export type LlmModelOption = {
  id: string;
  label: string;
};

export type LlmProviderOption = {
  id: string;
  label: string;
  region: "cn" | "intl";
  models: LlmModelOption[];
};

export type LlmModelsResponse = {
  providers: LlmProviderOption[];
  default: string;
};

export async function fetchLlmModels(): Promise<LlmModelsResponse> {
  const { data } = await client.get<LlmModelsResponse>("/config/llm-models");
  return data;
}

/** 将 provider:model 转为可读标签 */
export function formatAiModelLabel(value: string, catalog?: LlmModelsResponse): string {
  const [providerId, modelId] = value.includes(":") ? value.split(":", 2) : ["", value];
  const provider = catalog?.providers.find((p) => p.id === providerId);
  if (provider) {
    const model = provider.models.find((m) => m.id === modelId);
    return model ? `${provider.label} · ${model.label}` : `${provider.label} · ${modelId}`;
  }
  return value;
}

/** 规范化旧格式 ai_model（如 qwen-max）为 provider:model */
export function normalizeAiModelValue(value: string | null | undefined, catalog?: LlmModelsResponse): string {
  const raw = (value ?? "").trim();
  if (!raw) return catalog?.default ?? "deepseek:deepseek-chat";
  if (raw.includes(":")) return raw;

  for (const provider of catalog?.providers ?? []) {
    if (provider.models.some((m) => m.id === raw)) {
      return `${provider.id}:${raw}`;
    }
  }
  return raw;
}

/** 当前值是否在 catalog 可选列表中 */
export function isKnownAiModel(value: string, catalog?: LlmModelsResponse): boolean {
  if (!catalog?.providers.length) return false;
  const normalized = normalizeAiModelValue(value, catalog);
  const [providerId, modelId] = normalized.split(":", 2);
  return catalog.providers.some(
    (p) => p.id === providerId && p.models.some((m) => m.id === modelId),
  );
}
