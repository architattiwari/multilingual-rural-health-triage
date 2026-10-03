// Thin API client with timeouts. Only idempotent GETs are retried automatically: a retried POST
// could submit a patient message twice, so the UI offers an explicit "try again" instead.

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const BASE = (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? "";
const V1 = `${BASE}/api/v1`;

export interface Question { question_id: string; kind: string; text: string; required_for_triage: boolean }
export interface PatientResult {
  level: "emergency" | "urgent" | "non_urgent"; language: string; headline: string; message: string;
  next_steps: string[]; warning_signs: string[]; disclaimer: string; emergency_contact: { number: string; label: string } | null;
}
export interface Turn {
  conversation_id: string; triage_status: string; assistant_message: string; question: Question | null;
  triage: { patient: PatientResult } | null; state: { language: string }; disclaimer: string;
}
export interface Created { conversation_id: string; access_token: string; language: string; assistant_message: string; disclaimer: string; emergency_contact: { number: string; label: string } | null }
export interface Transcript { text: string; usable: boolean; low_confidence: boolean; warnings: string[] }
export interface Meta { limits: { max_audio_seconds: number; max_text_chars: number }; providers: Record<string, boolean>; emergency_contact: { number: string; label: string } | null }

interface Options { method?: string; body?: BodyInit; json?: unknown; token?: string; timeoutMs?: number; retries?: number }

async function request<T>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const attempts = (method === "GET" ? (opts.retries ?? 2) : 0) + 1;
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? 20_000);
    try {
      const headers: Record<string, string> = {};
      if (opts.token) headers["X-Conversation-Token"] = opts.token;
      if (opts.json !== undefined) headers["Content-Type"] = "application/json";
      const res = await fetch(`${V1}${path}`, {
        method, headers, signal: controller.signal,
        body: opts.json !== undefined ? JSON.stringify(opts.json) : opts.body,
      });
      if (res.ok) return (res.status === 204 ? undefined : res.headers.get("content-type")?.includes("json") ? await res.json() : res) as T;
      let code = "http_error";
      let message = "";
      try {
        const payload = await res.json();
        code = payload?.error?.code ?? code;
        message = payload?.error?.message ?? "";
      } catch { /* body was not JSON */ }
      if (res.status >= 500 && attempt + 1 < attempts) { lastError = new ApiError(code, res.status, message); continue; }
      throw new ApiError(code, res.status, message);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      lastError = new ApiError((err as Error).name === "AbortError" ? "timeout" : "network", 0, "");
      if (attempt + 1 >= attempts) throw lastError;
      await new Promise((r) => setTimeout(r, 400 * (attempt + 1)));
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastError;
}

export const api = {
  meta: () => request<Meta>("/meta"),
  create: (language: string) => request<Created>("/conversations", { method: "POST", json: { language } }),
  get: (id: string, token: string) => request<{ triage_status: string; messages: { role: string; text: string }[]; pending_question: Question | null; state: { language: string } }>(`/conversations/${id}`, { token }),
  message: (id: string, token: string, text: string, source: "text" | "voice", languageHint: string) =>
    request<Turn>(`/conversations/${id}/messages`, { method: "POST", token, json: { text, source, language_hint: languageHint } }),
  transcribe: (id: string, token: string, blob: Blob, languageHint: string) => {
    const form = new FormData();
    form.append("audio", blob, "recording");
    form.append("language_hint", languageHint);
    return request<Transcript>(`/conversations/${id}/audio/transcribe`, { method: "POST", token, body: form, timeoutMs: 45_000 });
  },
  speech: async (id: string, token: string): Promise<Blob> => {
    const res = await request<Response>(`/conversations/${id}/speech`, { method: "POST", token, timeoutMs: 30_000 });
    return res.blob();
  },
  remove: (id: string, token: string) => request<void>(`/conversations/${id}`, { method: "DELETE", token }),
};

/** Map an error to the translation key shown to the patient. Never shows raw server text. */
export function errorKey(err: unknown): "errNetwork" | "errTimeout" | "errRate" | "errSession" | "errServer" | "errVoice" | "errAudio" | "errInput" {
  if (!(err instanceof ApiError)) return "errServer";
  switch (err.code) {
    case "network": return "errNetwork";
    case "timeout": return "errTimeout";
    case "rate_limited": return "errRate";
    case "unauthorized": return "errSession";
    case "provider_unavailable": return "errVoice";
    case "unsupported_media": case "payload_too_large": return "errAudio";
    case "validation_failed": return err.status === 422 ? "errInput" : "errServer";
    default: return "errServer";
  }
}
