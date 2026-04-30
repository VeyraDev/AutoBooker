import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { UserInfo } from "@/types/auth";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserInfo | null;
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: UserInfo | null) => void;
  logout: () => void;
  tryRefresh: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),
      setUser: (user) => set({ user }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
      tryRefresh: async () => {
        const refresh = get().refreshToken;
        if (!refresh) return false;
        try {
          const base = import.meta.env.VITE_API_BASE ?? "";
          const res = await fetch(`${base}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refresh }),
          });
          if (!res.ok) return false;
          const data = (await res.json()) as {
            access_token: string;
            refresh_token: string;
          };
          set({
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
          });
          return true;
        } catch {
          return false;
        }
      },
    }),
    {
      name: "autobooker-auth",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    }
  )
);
