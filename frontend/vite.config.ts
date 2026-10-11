import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { pwaPlugin } from "./build/pwaPlugin.mjs";
const proxy = {
  "/rest-api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/rest-api/, ""),
  },
  "/illustration-api": {
    target: "http://127.0.0.1:8766",
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/illustration-api/, ""),
  },
};
export default defineConfig(({ mode }) => ({
  plugins: [react(), pwaPlugin()],
  // Model access is an explicit phone-model mode; ordinary phone mode stays UI-only.
  define:
    mode === "phone" || mode === "phone-model"
      ? {
          "import.meta.env.VITE_REST_API_URL": JSON.stringify(""),
          "import.meta.env.VITE_PHONE_PREVIEW": JSON.stringify("true"),
          "import.meta.env.VITE_PHONE_MODEL_ENABLED": JSON.stringify(
            mode === "phone-model" ? "true" : "false",
          ),
        }
      : {},
  server: {
    host: "127.0.0.1",
    proxy: mode === "phone" ? { "/rest-api": proxy["/rest-api"] } : proxy,
  },
  preview: { host: "127.0.0.1", proxy },
}));
