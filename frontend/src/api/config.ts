import { client } from "@/api/client";

export type LlmModelOption = {
  id: string;
  label: string;
  value?: string;
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

export function aiModelOptionValue(provider: LlmProviderOption, model: LlmModelOption): string {
  return model.value ?? `${provider.id}:${model.id}`;
}

/** 将 provider:model 转为可读标签 */
export function formatAiModelLabel(value: string, catalog?: LlmModelsResponse): string {
  const [providerId, modelId] = value.includes(":") ? value.split(":", 2) : ["", value];
  const provider = catalog?.providers.find((p) => p.id === providerId);
  if (provider) {
    const model = provider.models.find((m) => m.id === modelId || aiModelOptionValue(provider, m) === value);
    return model ? `${provider.label} · ${model.label}` : `${provider.label} · ${modelId}`;
  }
  for (const provider of catalog?.providers ?? []) {
    const model = provider.models.find((m) => aiModelOptionValue(provider, m) === value);
    if (model) return `${provider.label} · ${model.label}`;
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
      const model = provider.models.find((m) => m.id === raw)!;
      return aiModelOptionValue(provider, model);
    }
  }
  return raw;
}

/** 当前值是否在 catalog 可选列表中 */
export function isKnownAiModel(value: string, catalog?: LlmModelsResponse): boolean {
  if (!catalog?.providers.length) return false;
  const normalized = normalizeAiModelValue(value, catalog);
  return catalog.providers.some((p) =>
    p.models.some((m) => aiModelOptionValue(p, m) === normalized),
  );
}
