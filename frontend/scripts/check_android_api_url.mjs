import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const envFile = path.join(root, ".env.production");
if (fs.existsSync(envFile)) {
  for (const line of fs.readFileSync(envFile, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const [key, ...rest] = trimmed.split("=");
    if (!(key in process.env)) process.env[key] = rest.join("=");
  }
}
const mode = process.env.ANDROID_API_MODE ?? "cloud";
const allowLocalHttp = process.env.VITE_ALLOW_LOCAL_HTTP === "true" || mode === "local";
const apiBase = (process.env.VITE_API_BASE_URL ?? "").trim();

const failures = [];

if (!apiBase) {
  failures.push("VITE_API_BASE_URL is required for Android builds.");
}

if (/\/api\/v1\/api\/v1\b/.test(apiBase)) {
  failures.push("VITE_API_BASE_URL contains duplicate /api/v1/api/v1.");
}

if (!allowLocalHttp && /^http:\/\//i.test(apiBase)) {
  failures.push("Cloud Android builds must use HTTPS. Set VITE_ALLOW_LOCAL_HTTP=true only for LAN testing.");
}

if (!allowLocalHttp && /(localhost|127\.0\.0\.1|0\.0\.0\.0)/i.test(apiBase)) {
  failures.push("Cloud Android builds cannot point to localhost or loopback.");
}

if (/trycloudflare\.com/i.test(apiBase)) {
  failures.push("Stale Cloudflare tunnel URL detected in VITE_API_BASE_URL.");
}

const distDir = path.join(root, "dist");
if (fs.existsSync(distDir)) {
  const stalePatterns = [
    /trycloudflare\.com/i,
    /\/api\/v1\/api\/v1\b/i,
  ];
  if (!allowLocalHttp) {
    stalePatterns.push(/https?:\/\/localhost:8000\b/i, /https?:\/\/127\.0\.0\.1:8000\b/i);
  }
  const files = [];
  function walk(dir) {
    for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, item.name);
      if (item.isDirectory()) walk(full);
      else if (/\.(js|html|css|json)$/.test(item.name)) files.push(full);
    }
  }
  walk(distDir);
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of stalePatterns) {
      if (pattern.test(text)) {
        failures.push(`Built asset contains forbidden API pattern ${pattern}: ${path.relative(root, file)}`);
      }
    }
  }
}

if (failures.length > 0) {
  console.error("Android API URL validation failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`Android API URL validation passed for ${mode} mode: ${apiBase}`);
