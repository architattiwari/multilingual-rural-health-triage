import { h } from "../dom";
import { t } from "../i18n";
import { state } from "../store";
import { contactNode, disclaimerBlock, notice, topbar } from "./common";

export function renderWelcome(onStart: () => void, onLang: (l: "hi" | "en") => void): HTMLElement {
  const list = (...keys: Parameters<typeof t>[0][]) => h("ul", { class: "plain" }, ...keys.map((k) => h("li", {}, t(k))));
  return h("div", { class: "shell" },
    topbar(onLang),
    h("main", { id: "main" },
      h("h1", { tabindex: "-1", "data-autofocus": "" }, t("welcomeTitle")),
      h("p", {}, t("welcomeLead")),
      notice(),
      h("div", { class: "row" }, h("button", { class: "btn", type: "button", onClick: onStart, disabled: state.busy !== null }, t("start"))),
      h("section", { class: "card" }, h("h2", {}, t("does")), list("does1", "does2", "does3")),
      h("section", { class: "card" }, h("h2", {}, t("doesNot")), list("not1", "not2", "not3")),
      // Static content so it is readable offline from the cached shell.
      h("section", { class: "card notice" }, h("h2", {}, t("emergencyTitle")), h("p", {}, t("emergencyLead")),
        h("ul", { class: "plain" },
          ...(state.lang === "hi"
            ? ["सांस लेने में बहुत दिक्कत", "सीने में दर्द", "बेहोशी या बहुत ज्यादा उलझन", "चेहरा टेढ़ा, एक तरफ कमजोरी या बोलने में दिक्कत", "दौरा या झटके", "बहुत ज्यादा खून बहना", "सांप का काटना या जहर खा लेना"]
            : ["Severe difficulty breathing", "Chest pain", "Fainting or severe confusion", "Drooping face, one sided weakness or trouble speaking", "Seizure or convulsions", "Heavy bleeding", "Snake bite or swallowed poison"]
          ).map((s) => h("li", {}, s))),
        contactNode(state.meta?.emergency_contact)),
      disclaimerBlock()));
}
