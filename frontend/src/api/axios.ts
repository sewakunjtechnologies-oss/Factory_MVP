import axios, { AxiosError } from "axios";

import { useAuthStore } from "../store/authStore";

export const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

function normalizeApiBaseUrl(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, "");
  if (!trimmed) return DEFAULT_API_BASE_URL;
  return trimmed.endsWith("/api/v1") ? trimmed : `${trimmed}/api/v1`;
}

export function getApiBaseUrl(): string {
  return normalizeApiBaseUrl(DEFAULT_API_BASE_URL);
}

export function setApiBaseUrl(value: string): string {
  const normalized = normalizeApiBaseUrl(value);
  api.defaults.baseURL = normalized;
  return normalized;
}

export const API_BASE_URL = getApiBaseUrl();

export const API_ORIGIN = (() => {
  try {
    return new URL(getApiBaseUrl()).origin;
  } catch {
    return "";
  }
})();

export function resolveAssetUrl(url: string | null | undefined): string {
  if (!url) return "";
  if (/^(?:https?:)?\/\//i.test(url) || url.startsWith("data:")) return url;
  if (url.startsWith("/")) {
    try {
      return `${new URL(getApiBaseUrl()).origin}${url}`;
    } catch {
      return url;
    }
  }
  return url;
}

export const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  },
);

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (error.code === "ERR_NETWORK") {
      return `Cannot reach the factory server at ${getApiBaseUrl()}. Check that the backend is running on port 8000.`;
    }
    if (error.code === "ECONNABORTED") {
      return `The factory server did not respond in time at ${getApiBaseUrl()}.`;
    }
    return error.message;
  }
  return "Something went wrong";
}
