import { h, micIcon } from "../dom";
import { t } from "../i18n";
import { recordingSupported } from "../recorder";
import { state } from "../store";
import { disclaimerBlock, notice, topbar } from "./common";

export interface ChatActions {
  onLang: (l: "hi" | "en") => void;
  onMic: () => void;
  onSend: () => void;
  onDraft: (text: string) => void;
  onListen: () => void;
}

export function renderChat(a: ChatActions): HTMLElement {
  const maxChars = state.meta?.limits.max_text_chars ?? 1000;
  const voiceAvailable = recordingSupported() && state.meta?.providers.speech_to_text !== false;
  const recording = state.busy === "recording";

  const history = h("ol", { class: "history", "aria-label": t("helper") },
    ...state.history.map((m) => h("li", { class: `msg ${m.role}` },
      h("span", { class: "who" }, m.role === "assistant" ? t("helper") : t("you")), m.text)));

  const mic = h("div", { class: "mic-wrap" },
    h("button", { class: recording ? "mic recording" : "mic", type: "button", onClick: a.onMic, disabled: state.busy === "processing" || state.busy === "sending",
                  "aria-label": recording ? t("micStop") : t("micStart"), "aria-pressed": String(recording) }, micIcon()),
    h("span", { class: "hint" }, recording ? t("recording") : state.busy === "processing" ? t("processing") : t("micStart")));

  const textarea = h("textarea", { id: "draft", maxlength: maxChars, "data-autofocus": "", lang: state.lang, onInput: (e: Event) => a.onDraft((e.target as HTMLTextAreaElement).value) });
  textarea.value = state.draft;

  const listen = h("button", { class: "btn secondary", type: "button", onClick: a.onListen }, state.speaking ? t("stopListening") : t("listen"));

  return h("div", { class: "shell" },
    topbar(a.onLang),
    h("main", { id: "main" },
      history,
      notice(),
      listen,
      voiceAvailable ? mic : h("p", { class: "hint" }, t("micUnsupported")),
      h("label", { for: "draft" }, state.draftSource === "voice" && state.draft ? t("weHeard") : t("typeHere")),
      textarea,
      h("div", { class: "row", style: "margin-top:12px" },
        h("button", { class: "btn", type: "button", onClick: a.onSend, disabled: !state.draft.trim() || state.busy !== null }, state.busy === "sending" ? t("sending") : t("send"))),
      disclaimerBlock()));
}
