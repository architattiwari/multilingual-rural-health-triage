import { dialable, h } from "../dom";
import { t } from "../i18n";
import { state } from "../store";

export function topbar(onLang: (l: "hi" | "en") => void): HTMLElement {
  const seg = h("div", { class: "seg", role: "group", "aria-label": t("language") },
    h("button", { type: "button", "aria-pressed": String(state.lang === "hi"), lang: "hi", onClick: () => onLang("hi") }, "हिन्दी"),
    h("button", { type: "button", "aria-pressed": String(state.lang === "en"), lang: "en", onClick: () => onLang("en") }, "English"));
  return h("header", { class: "topbar" },
    h("span", { class: "brand" }, t("appName")),
    h("span", { class: "status" }, h("span", { class: state.online ? "dot" : "dot off", "aria-hidden": "true" }), state.online ? t("online") : t("offline")),
    seg);
}

export function disclaimerBlock(text?: string): HTMLElement {
  return h("p", { class: "disclaimer" }, text || t("disclaimer"));
}

export function contactNode(contact: { number: string; label: string } | null | undefined): HTMLElement {
  if (!contact) return h("p", {}, t("emergencyContactMissing"));
  const label = contact.label ? `${contact.label} ` : "";
  const href = dialable(contact.number);
  return h("p", {}, `${t("emergencyContact")}: `, href ? h("a", { class: "contact", href: `tel:${href}` }, `${label}${contact.number}`) : `${label}${contact.number}`);
}

export function notice(): HTMLElement | null {
  return state.notice ? h("div", { class: "alert", role: "alert" }, state.notice) : null;
}
