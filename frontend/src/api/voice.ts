import { api, getApiBaseUrl } from "./axios";

export interface VoiceArtifact {
  type: string;
  title?: string | null;
  download_url?: string | null;
  report_type?: string | null;
  report_id?: string | null;
}

export interface VoiceAskResponse {
  answer: string;
  speech_text?: string | null;
  artifacts: VoiceArtifact[];
  pending_action?: {
    action_id: string;
    intent: string;
    po_number?: string | null;
    entities: Record<string, unknown>;
    missing_fields: string[];
    confirmation_message?: string | null;
  } | null;
  requires_confirmation?: boolean;
}

export async function askAssistant(message: string): Promise<VoiceAskResponse> {
  const response = await api.post<VoiceAskResponse>("/voice/ask", { message });
  return response.data;
}

// Strip the API_BASE_URL path prefix (e.g. "/api/v1") so axios doesn't double it.
function toRelativeApiPath(fullPath: string): string {
  try {
    const basePrefix = new URL(getApiBaseUrl()).pathname.replace(/\/$/, "");
    if (basePrefix && fullPath.startsWith(basePrefix + "/")) {
      return fullPath.slice(basePrefix.length);
    }
  } catch {
    /* ignore */
  }
  return fullPath;
}

/**
 * Fetch an authed download URL as a Blob. The plain <a href> approach fails
 * because browsers don't attach the JWT bearer token to anchor-tag requests,
 * so the backend's require_owner guard returns 401. Axios does attach it.
 */
export async function fetchArtifactBlob(downloadUrl: string): Promise<Blob> {
  const path = toRelativeApiPath(downloadUrl);
  const response = await api.get<Blob>(path, { responseType: "blob" });
  return response.data;
}
