import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Factory Control — Android packaging via Capacitor.
 *
 * The app is a thin native shell that loads the React PWA. Two modes:
 *
 * 1. **Production (default)** — `webDir` is the static `dist/` bundle and the
 *    APK ships with the React build embedded. The shell hits whatever API
 *    base URL is hardcoded into `dist/`.
 *
 * 2. **Live-reload during dev** — uncomment the `server.url` block and the
 *    APK loads from your Mac's dev server (faster iteration, no rebuild).
 *    The phone must be on the same Wi-Fi as the Mac. Run:
 *      npm run dev -- --host 0.0.0.0
 *    then set `server.url` to `http://<your-mac-lan-ip>:5173`.
 */
const config: CapacitorConfig = {
  appId: "com.factorymvp.control",
  appName: "Factory Control",
  webDir: "dist",
  bundledWebRuntime: false,
  android: {
    // Cloud builds require HTTPS. Local LAN test builds can opt in with
    // VITE_ALLOW_LOCAL_HTTP=true.
    allowMixedContent: process.env.VITE_ALLOW_LOCAL_HTTP === "true",
  },
  // server: {
  //   url: "http://192.168.1.50:5173",
  //   cleartext: true,
  // },
};

export default config;
