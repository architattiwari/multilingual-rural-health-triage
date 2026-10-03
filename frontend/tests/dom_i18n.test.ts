import { describe, expect, it } from "vitest";
import { dialable, h } from "../src/dom";
import { ALL_STRINGS } from "../src/i18n";

describe("dom helpers", () => {
  it("never interprets text as markup", () => {
    const el = h("p", {}, '<img src=x onerror="alert(1)">');
    expect(el.querySelector("img")).toBeNull();
    expect(el.textContent).toContain("<img");
  });
  it("sanitises phone numbers for tel links", () => {
    const out = dialable("1 0 8 javascript:alert(1)");
    expect(out).toMatch(/^[0-9+*#]*$/); // only dialable characters, so no URL scheme can survive
    expect(out).not.toContain("javascript");
    expect(dialable("+91 98765-43210")).toBe("+919876543210");
  });
});

describe("translations", () => {
  it("has identical keys in Hindi and English with no empty values", () => {
    expect(Object.keys(ALL_STRINGS.hi).sort()).toEqual(Object.keys(ALL_STRINGS.en).sort());
    for (const lang of ["hi", "en"] as const) for (const [k, v] of Object.entries(ALL_STRINGS[lang])) expect(v.length, `${lang}.${k}`).toBeGreaterThan(0);
  });
  it("states the medical disclaimer in both languages", () => {
    expect(ALL_STRINGS.en.disclaimer).toContain("does not diagnose");
    expect(ALL_STRINGS.hi.disclaimer).toContain("पहचान नहीं");
  });
});
