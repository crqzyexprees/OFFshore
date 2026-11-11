import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const API_URL = `http://127.0.0.1:${process.env.SPLITLENS_API_PORT ?? "18765"}`;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./",
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    proxy: {
      "/api": API_URL,
      "/health": API_URL,
    },
  },
});
