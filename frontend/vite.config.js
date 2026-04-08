import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev port: set in vite.config below, or override with CLI / env.
//   npm run dev -- --port 3000
//   FRONTEND_PORT=3000 npm run dev
const devPort = Number(process.env.FRONTEND_PORT || 5173) || 5173;

export default defineConfig({
  plugins: [react()],
  server: {
    port: devPort,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
});
