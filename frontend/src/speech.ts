import { api } from "./api";
import type { Lang } from "./i18n";

let audio: HTMLAudioElement | null = null;
let objectUrl: string | null = null;

export function stopSpeaking(): void {
  audio?.pause();
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  audio = null;
  objectUrl = null;
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

/** Play the latest assistant message. Uses the server voice, then the device voice, else reports failure. */
export async function speak(conversationId: string, token: string, text: string, lang: Lang, onEnd: () => void): Promise<boolean> {
  stopSpeaking();
  try {
    const blob = await api.speech(conversationId, token);
    objectUrl = URL.createObjectURL(blob);
    audio = new Audio(objectUrl);
    audio.onended = onEnd;
    await audio.play();
    return true;
  } catch {
    // Server voice unavailable: fall back to the voice built into the phone, which works with weak connectivity.
    if (!("speechSynthesis" in window)) return false;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === "hi" ? "hi-IN" : "en-IN";
    utterance.onend = onEnd;
    window.speechSynthesis.speak(utterance);
    return true;
  }
}
