var _a;
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
var API_TARGET = (_a = process.env.VITE_PROXY_TARGET) !== null && _a !== void 0 ? _a : "http://127.0.0.1:8001";
var API_PREFIXES = [
    "/auth",
    "/books",
    "/book-jobs",
    "/library",
    "/feedback",
    "/notifications",
    "/config",
    "/health",
    "/static/figures",
];
var proxy = Object.fromEntries(API_PREFIXES.map(function (prefix) { return [
    prefix,
    {
        target: API_TARGET,
        changeOrigin: true,
        timeout: 300000,
        proxyTimeout: 300000,
    },
]; }));
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        port: 5173,
        proxy: proxy,
    },
});
