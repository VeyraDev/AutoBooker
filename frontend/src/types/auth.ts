export interface UserInfo {
  id: string;
  email: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
