import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  /** .tsx/.ts vor .js — verhindert, dass alte Kompilate (App.js) statt App.tsx geladen werden. */
  resolve: {
    extensions: [".tsx", ".ts", ".jsx", ".mjs", ".js", ".mts", ".json"]
  },
  server: {
    port: 5173,
    strictPort: true
  }
});
