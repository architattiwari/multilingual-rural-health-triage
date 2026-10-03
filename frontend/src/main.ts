import "./styles.css";
import { api, ApiError, errorKey } from "./api";
import { announce, mount } from "./dom";
import { getLang, setLang, t, type Lang } from "./i18n";
import { Recorder } from "./recorder";
import { renderChat } from "./screens/chat";
import { renderResult } from "./screens/result";
import { renderWelcome } from "./screens/welcome";
import { speak, stopSpeaking } from "./speech";
import { loadSession, saveSession, state } from "./store";

const root = document.getElementById("app") as HTMLElement;
let recorder: Recorder | null = null;


function render(): void {
  const keepFocus = document.activeElement?.id;
  const selection = keepFocus === "draft" ? (document.activeElement as HTMLTextAreaElement).selectionStart : null;
  const onLang = (l: Lang) => { setLang(l); localStorage.setItem("triage.lang", l); state.lang = l; state.notice = null; render(); };
  const screen =
    state.screen === "welcome" ? renderWelcome(startConversation, onLang)
    : state.screen === "chat" ? renderChat({ onLang, onMic: toggleMic, onSend: sendDraft, onDraft: (v) => { state.draft = v; state.draftSource = state.draftSource === "voice" && !v ? "text" : state.draftSource; refreshSendButton(); }, onListen: listen })
    : renderResult({ onLang, onListen: listen, onRestart: restart, onDelete: deleteData });
  mount(root, screen);
  const focusTarget = keepFocus === "draft" && document.getElementById("draft") ? document.getElementById("draft") : root.querySelector<HTMLElement>("[data-autofocus]");
  if (focusTarget) {
    focusTarget.focus({ preventScroll: keepFocus === "draft" });
    if (selection !== null && focusTarget instanceof HTMLTextAreaElement) focusTarget.setSelectionRange(selection, selection);
  }
}

// Typing must not re-render the page (it would drop the caret), so only the send button is updated.
function refreshSendButton(): void {
  const send = root.querySelector<HTMLButtonElement>(".row .btn:not(.secondary):not(.link)");
  if (send) send.disabled = !state.draft.trim() || state.busy !== null;
}

function fail(err: unknown): void {
  state.notice = t(errorKey(err));
  state.busy = null;
  render();
  announce(state.notice);
}

async function startConversation(): Promise<void> {
  state.busy = "sending"; state.notice = null; render();
  try {
    const created = await api.create(state.lang);
    state.session = { id: created.conversation_id, token: created.access_token };
    saveSession();
    state.history = [{ role: "assistant", text: created.assistant_message }];
    state.screen = "chat"; state.busy = null;
    render();
    announce(created.assistant_message);
  } catch (err) { fail(err); }
}

function applyTurn(turn: Awaited<ReturnType<typeof api.message>>): void {
  state.history.push({ role: "assistant", text: turn.assistant_message });
  state.question = turn.question;
  state.draft = ""; state.draftSource = "text"; state.busy = null; state.notice = null;
  if (turn.triage) { state.result = turn.triage.patient; state.screen = "result"; }
  render();
  announce(turn.assistant_message);
}

async function sendDraft(): Promise<void> {
  const text = state.draft.trim();
  if (!text || !state.session) return;
  state.history.push({ role: "patient", text });
  state.busy = "sending"; state.notice = null; render();
  try {
    applyTurn(await api.message(state.session.id, state.session.token, text, state.draftSource, getLang()));
  } catch (err) {
    state.history.pop(); // the message was not accepted, let the patient resend it
    state.draft = text;
    fail(err);
  }
}

async function toggleMic(): Promise<void> {
  if (!state.session) return;
  if (state.busy === "recording" && recorder) {
    const rec = recorder; recorder = null;
    state.busy = "processing"; render();
    try {
      const blob = await rec.stop();
      const out = await api.transcribe(state.session.id, state.session.token, blob, getLang());
      state.busy = null;
      if (!out.text.trim()) { state.notice = t("noSpeech"); }
      else { state.draft = out.text; state.draftSource = "voice"; state.notice = out.low_confidence ? t("lowConfidence") : null; }
      render();
    } catch (err) { fail(err); }
    return;
  }
  try {
    stopSpeaking(); state.speaking = false;
    recorder = new Recorder(state.meta?.limits.max_audio_seconds ?? 60);
    await recorder.start(() => { if (state.busy === "recording") void toggleMic(); });
    state.busy = "recording"; state.notice = null; render();
  } catch {
    recorder = null; state.busy = null; state.notice = t("micDenied"); render();
  }
}

async function listen(): Promise<void> {
  if (state.speaking) { stopSpeaking(); state.speaking = false; render(); return; }
  if (!state.session) return;
  const text = state.screen === "result" && state.result ? `${state.result.headline}. ${state.result.message}` : state.history.filter((m) => m.role === "assistant").at(-1)?.text ?? "";
  if (!text) return;
  state.speaking = true; render();
  const ok = await speak(state.session.id, state.session.token, text, getLang(), () => { state.speaking = false; render(); });

  if (!ok) { state.speaking = false; state.notice = t("listenUnavailable"); render(); }
}

async function endSession(): Promise<void> {
  stopSpeaking();
  const s = state.session;
  state.session = null; saveSession();
  if (s) await api.remove(s.id, s.token).catch(() => undefined);
}

async function restart(): Promise<void> {
  await endSession();
  Object.assign(state, { screen: "welcome", history: [], question: null, result: null, draft: "", notice: null, busy: null, speaking: false });
  render();
}

async function deleteData(): Promise<void> {
  await endSession();
  Object.assign(state, { screen: "welcome", history: [], question: null, result: null, draft: "", busy: null, speaking: false, notice: t("deleted") });
  render();
}

async function resume(): Promise<void> {
  const saved = loadSession();
  if (!saved) return;
  try {
    const conv = await api.get(saved.id, saved.token);
    state.session = saved;
    state.history = conv.messages.map((m) => ({ role: m.role as "assistant" | "patient", text: m.text }));
    state.question = conv.pending_question;
    state.screen = "chat";
  } catch (err) {
    if (err instanceof ApiError && err.code === "unauthorized") { state.session = null; saveSession(); }
  }
}

async function init(): Promise<void> {
  const stored = localStorage.getItem("triage.lang");
  state.lang = stored === "en" ? "en" : "hi"; setLang(state.lang);
  window.addEventListener("online", () => { state.online = true; render(); });
  window.addEventListener("offline", () => { state.online = false; render(); });
  render();
  // Metadata and resume are best effort. The welcome screen is already usable without them.
  state.meta = await api.meta().catch(() => null);
  await resume();
  render();
  if ("serviceWorker" in navigator && import.meta.env.PROD) navigator.serviceWorker.register("/sw.js").catch(() => undefined);
}

void init();
