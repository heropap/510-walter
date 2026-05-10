import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: process.env.APP_BASE_PATH ? `${process.env.APP_BASE_PATH.replace(/\/$/, "")}/` : "/",
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:7860",
      "/health": "http://localhost:7860"
    }
  }
});
