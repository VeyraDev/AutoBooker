export interface UserAiModels {
  outline_ai_model: string | null;
  constitution_ai_model: string | null;
  writing_ai_model: string | null;
  assistant_ai_model: string | null;
}

export interface UserInfo {
  id: string;
  email: string;
  ai_models: UserAiModels;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export type UserAiModelsPatch = Partial<UserAiModels>;
