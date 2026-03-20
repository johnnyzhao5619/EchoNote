import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Tauri 开发服务器配置
  server: {
    port: 1420,
    strictPort: true,
    host: "localhost",
    hmr: {
      protocol: "ws",
      host: "localhost",
      port: 1421,
    },
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
  clearScreen: false,
  envPrefix: ["VITE_", "TAURI_"],
  // Vitest 配置
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    css: true,
  },
});
