/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

/**
 * 靜態打包設定（無 API / 無 .env）
 * 將 api.ts 替換為 api.mock.ts，輸出到 dist-static/
 * 可直接用任何靜態伺服器開啟（不需後端）。
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // 攔截所有對 api.ts 的 import，導向 mock 版本（不需 API / 不需 .env）
      [path.resolve(__dirname, "src/services/api.ts")]: path.resolve(__dirname, "src/services/api.mock.ts"),
    },
  },
  define: {
    // 可在前端程式碼中用 import.meta.env.VITE_STATIC_MODE 判斷
    "import.meta.env.VITE_STATIC_MODE": JSON.stringify("true"),
  },
  build: {
    outDir: "dist-static",
    emptyOutDir: true,
  },
  // 靜態版本不需要 proxy
});
