import { client } from "@/api/client";
import type { TokenPair, UserAiModelsPatch, UserInfo } from "@/types/auth";

const jsonHeaders = { "Content-Type": "application/json" } as const;

export async function registerApi(email: string, password: string): Promise<TokenPair> {
  const { data } = await client.post<TokenPair>("/auth/register", { email, password }, { headers: jsonHeaders });
  return data;
}

export async function loginApi(email: string, password: string): Promise<TokenPair> {
  const { data } = await client.post<TokenPair>("/auth/login", { email, password }, { headers: jsonHeaders });
  return data;
}

export async function meApi(): Promise<UserInfo> {
  const { data } = await client.get<UserInfo>("/auth/me");
  return data;
}

export async function patchUserAiModels(payload: UserAiModelsPatch): Promise<UserInfo> {
  const { data } = await client.patch<UserInfo>("/auth/me/ai-models", payload);
  return data;
}
