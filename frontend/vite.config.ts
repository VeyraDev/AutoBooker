import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const API_TARGET = process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8001";

const API_PREFIXES = [
  "/auth",
  "/books",
  "/book-jobs",
  "/library",
  "/feedback",
  "/notifications",
  "/config",
  "/health",
  "/static/figures",
] as const;

const proxy = Object.fromEntries(
  API_PREFIXES.map((prefix) => [
    prefix,
    {
      target: API_TARGET,
      changeOrigin: true,
      timeout: 300_000,
      proxyTimeout: 300_000,
    },
  ]),
);

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy,
  },
});
