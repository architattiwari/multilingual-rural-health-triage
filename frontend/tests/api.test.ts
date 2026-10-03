import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, errorKey } from "../src/api";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("api client", () => {
  beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
  afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

  it("sends the conversation token header and JSON body", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ assistant_message: "ok" }));
    await api.message("id", "tok", "bukhar", "text", "hi");
    const [url, init] = spy.mock.calls[0];
    expect(String(url)).toBe("/api/v1/conversations/id/messages");
    expect((init!.headers as Record<string, string>)["X-Conversation-Token"]).toBe("tok");
    expect(JSON.parse(init!.body as string)).toEqual({ text: "bukhar", source: "text", language_hint: "hi" });
  });

  it("retries GET on network failure but never retries POST", async () => {
    const get = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new TypeError("net")).mockResolvedValueOnce(json({ ok: 1 }));
    await expect(api.meta()).resolves.toEqual({ ok: 1 });
    expect(get).toHaveBeenCalledTimes(2);
    get.mockReset().mockRejectedValue(new TypeError("net"));
    await expect(api.message("i", "t", "x", "text", "hi")).rejects.toMatchObject({ code: "network" });
    expect(get).toHaveBeenCalledTimes(1);
  });

  it("surfaces server error codes without exposing server text to patients", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ error: { code: "unauthorized", message: "internal detail" } }, 401));
    const err = await api.get("i", "t").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(errorKey(err)).toBe("errSession");
  });

  it("times out slow requests", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((_u, init) => new Promise((_res, rej) => {
      (init!.signal as AbortSignal).addEventListener("abort", () => rej(Object.assign(new Error("a"), { name: "AbortError" })));
    }));
    const p = api.create("hi").catch((e) => e);
    await vi.advanceTimersByTimeAsync(21_000);
    expect(errorKey(await p)).toBe("errTimeout");
  });

  it("maps provider and media errors to friendly keys", () => {
    expect(errorKey(new ApiError("provider_unavailable", 503, ""))).toBe("errVoice");
    expect(errorKey(new ApiError("unsupported_media", 415, ""))).toBe("errAudio");
    expect(errorKey(new ApiError("rate_limited", 429, ""))).toBe("errRate");
    expect(errorKey(new Error("boom"))).toBe("errServer");
  });
});
