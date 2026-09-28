import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Admin-Web (Browser) — eigener Port, parallel zu Chat (5174) */
export default defineConfig({
  base: "./",
  plugins: [react()],
  resolve: {
    extensions: [".tsx", ".ts", ".jsx", ".mjs", ".js", ".mts", ".json"]
  },
  server: {
    port: 5175,
    strictPort: true
  },
  preview: {
    port: 5175,
    strictPort: true
  },
  build: {
    outDir: "dist",
    emptyOutDir: true
  }
});
