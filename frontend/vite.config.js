import { defineConfig } from "vite";

// Browser requests remain same-origin. Vite forwards /api during local development.
export default defineConfig({
  server: {
    port: 5176,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8003" },
  },
});
