/**
 * API client for the Minuta backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8741";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API error ${res.status}: ${error}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Types
export interface Meeting {
  id: string;
  title: string;
  status: "recording" | "transcribing" | "summarizing" | "completed" | "failed";
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  audio_source: string;
  transcript_segment_count: number;
  has_summary: boolean;
  summary_provider: string | null;
  webhook_sent: boolean;
  company: string;
  project: string;
  domain: string;
  tags: string[];
  notes: string;
}

export interface TranscriptSegment {
  id: string;
  meeting_id: string;
  index: number;
  speaker: string;
  source: string;
  text: string;
  start_time: number;
  end_time: number;
  confidence: number;
  language: string;
}

export interface Summary {
  id: string;
  meeting_id: string;
  provider: string;
  model: string;
  title: string;
  key_points: string[];
  action_items: string[];
  decisions: string[];
  sections: { heading: string; content: string }[];
  participants_mentioned: string[];
  full_text: string;
  language: string;
  token_count: number;
  generation_time_seconds: number;
}

export interface LicenseStatus {
  plan: string;
  is_pro: boolean;
  license_key: string | null;
  pro_features: string[];
}

export interface LLMProvider {
  id: string;
  name: string;
  model: string;
  configured: boolean;
  is_default: boolean;
}

// API methods
export const api = {
  // Health
  health: () => fetchApi<{ status: string; version: string; uptime_seconds: number }>("/api/health"),

  // Meetings
  listMeetings: (params?: { status?: string; limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.offset) searchParams.set("offset", String(params.offset));
    const qs = searchParams.toString();
    return fetchApi<Meeting[]>(`/api/meetings${qs ? `?${qs}` : ""}`);
  },

  createMeeting: (data: { title?: string; audio_source?: string; tags?: string[] }) =>
    fetchApi<Meeting>("/api/meetings", { method: "POST", body: JSON.stringify(data) }),

  getMeeting: (id: string) => fetchApi<Meeting>(`/api/meetings/${id}`),

  updateMeeting: (id: string, data: { title?: string; tags?: string[]; notes?: string }) =>
    fetchApi<Meeting>(`/api/meetings/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  deleteMeeting: (id: string) =>
    fetchApi<void>(`/api/meetings/${id}`, { method: "DELETE" }),

  stopMeeting: (id: string) =>
    fetchApi<Meeting>(`/api/meetings/${id}/stop`, { method: "POST" }),

  // Transcripts
  getTranscript: (meetingId: string) =>
    fetchApi<TranscriptSegment[]>(`/api/meetings/${meetingId}/transcript`),

  // Summaries
  summarizeMeeting: (meetingId: string, data?: { provider?: string; model?: string }) =>
    fetchApi<Summary>(`/api/meetings/${meetingId}/summarize`, {
      method: "POST",
      body: JSON.stringify(data || {}),
    }),

  getSummary: (meetingId: string) =>
    fetchApi<Summary>(`/api/meetings/${meetingId}/summary`),

  updateSummary: (meetingId: string, data: {
    title?: string; full_text?: string; key_points?: string[];
    action_items?: string[]; decisions?: string[];
  }) =>
    fetchApi<Summary>(`/api/meetings/${meetingId}/summary`, {
      method: "PUT", body: JSON.stringify(data),
    }),

  // Config
  getConfig: () => fetchApi<Record<string, unknown>>("/api/config"),
  getLLMProviders: () => fetchApi<LLMProvider[]>("/api/config/llm-providers"),

  // Webhook
  sendWebhook: (meetingId: string) =>
    fetchApi<void>(`/api/meetings/${meetingId}/webhook`, { method: "POST" }),

  // License
  getLicense: () => fetchApi<LicenseStatus>("/api/license"),

  activateLicense: (licenseKey: string) =>
    fetchApi<{ status: string; plan: string }>("/api/license/activate", {
      method: "POST",
      body: JSON.stringify({ license_key: licenseKey }),
    }),

  deactivateLicense: () =>
    fetchApi<{ status: string }>("/api/license/deactivate", { method: "POST" }),
};

// WebSocket
export function createTranscriptWS(meetingId: string): WebSocket {
  const wsUrl = (API_BASE.replace("http", "ws")) + `/ws/transcript/${meetingId}`;
  return new WebSocket(wsUrl);
}
