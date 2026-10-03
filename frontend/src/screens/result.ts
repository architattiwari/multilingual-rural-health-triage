import { h } from "../dom";
import { t } from "../i18n";
import { state } from "../store";
import { contactNode, disclaimerBlock, notice, topbar } from "./common";

export interface ResultActions { onLang: (l: "hi" | "en") => void; onListen: () => void; onRestart: () => void; onDelete: () => void }

const ICON = { emergency: "⚠", urgent: "●", non_urgent: "✓" } as const;

export function renderResult(a: ResultActions): HTMLElement {
  const r = state.result;
  if (!r) return h("div");
  const label = r.level === "emergency" ? t("levelEmergency") : r.level === "urgent" ? t("levelUrgent") : t("levelNonUrgent");
  return h("div", { class: "shell" },
    topbar(a.onLang),
    h("main", { id: "main" },
      // Level is conveyed by icon and words as well as colour.
      h("section", { class: `result ${r.level}`, "aria-labelledby": "result-title" },
        h("p", { class: "badge" }, h("span", { "aria-hidden": "true" }, ICON[r.level]), label),
        h("h1", { id: "result-title", tabindex: "-1", "data-autofocus": "" }, r.headline),
        h("p", {}, r.message)),
      r.level === "emergency" ? h("div", { class: "card" }, contactNode(r.emergency_contact)) : null,
      h("section", { class: "card" }, h("h2", {}, t("nextSteps")), h("ul", { class: "plain" }, ...r.next_steps.map((s) => h("li", {}, s)))),
      h("section", { class: "card" }, h("h2", {}, t("warningSigns")), h("ul", { class: "plain" }, ...r.warning_signs.map((s) => h("li", {}, s)))),
      notice(),
      h("div", { class: "row" },
        h("button", { class: "btn", type: "button", onClick: a.onListen }, state.speaking ? t("stopListening") : t("listen")),
        h("button", { class: "btn secondary", type: "button", onClick: a.onRestart }, t("startOver")),
        h("button", { class: "btn link", type: "button", onClick: a.onDelete }, t("deleteData"))),
      disclaimerBlock(r.disclaimer)));
}
