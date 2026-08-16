import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Pinned to 5173 on purpose — this is the port already whitelisted in
// backend/app/core/config.py's CORS_ORIGINS. Change both together.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
});
