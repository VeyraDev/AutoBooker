import axios, { type InternalAxiosRequestConfig } from "axios";

import { useAuthStore } from "@/stores/authStore";

export const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "",
  timeout: 15000,
});

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as RetriableConfig | undefined;
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      const refreshed = await useAuthStore.getState().tryRefresh();
      if (refreshed) {
        const newToken = useAuthStore.getState().accessToken;
        if (newToken) {
          original.headers.Authorization = `Bearer ${newToken}`;
        }
        return client(original);
      }
      useAuthStore.getState().logout();
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
