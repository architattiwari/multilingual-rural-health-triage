import type { Meta, PatientResult, Question } from "./api";
import type { Lang } from "./i18n";

export interface ChatLine { role: "assistant" | "patient"; text: string }

export interface AppState {
  screen: "welcome" | "chat" | "result";
  lang: Lang;
  meta: Meta | null;
  session: { id: string; token: string } | null;
  history: ChatLine[];
  question: Question | null;
  result: PatientResult | null;
  draft: string;
  draftSource: "text" | "voice";
  notice: string | null; // already translated, patient facing
  busy: "recording" | "processing" | "sending" | null;
  online: boolean;
  speaking: boolean;
}

export const state: AppState = {
  screen: "welcome", lang: "hi", meta: null, session: null, history: [], question: null, result: null,
  draft: "", draftSource: "text", notice: null, busy: null, online: navigator.onLine, speaking: false,
};

const KEY = "triage.session"; // holds only the opaque conversation id and token, tab scoped

export function saveSession(): void {
  try {
    if (state.session) sessionStorage.setItem(KEY, JSON.stringify(state.session));
    else sessionStorage.removeItem(KEY);
  } catch { /* storage may be disabled; the app still works for this page view */ }
}
export function loadSession(): { id: string; token: string } | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed && typeof parsed.id === "string" && typeof parsed.token === "string" ? parsed : null;
  } catch { return null; }
}
