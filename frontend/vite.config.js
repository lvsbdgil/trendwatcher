import { fileURLToPath } from "node:url";

import { defineConfig, loadEnv } from "vite";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectRoot, "");
  const backendTarget = env.VITE_API_URL || "http://127.0.0.1:8000";

  return {
    cacheDir: "node_modules/.vite",
    esbuild: {
      jsxFactory: "React.createElement",
      jsxFragment: "React.Fragment",
    },
    server: {
      fs: {
        strict: true,
        allow: [process.cwd()],
      },
      // Proxy API calls to the backend so the browser sees same-origin requests
      // and httpOnly cookies (SameSite=Lax) survive the round-trip.
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
          cookieDomainRewrite: "",
        },
      },
    },
  };
});
