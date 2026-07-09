import { describe, it, expect } from "vitest";
import { providerIcon } from "./providerIcon";

const FALLBACK =
  "https://gw.alicdn.com/imgextra/i4/O1CN01IWnlOw1lebfpiFrIL_!!6000000004844-0-tps-100-100.jpg";

describe("providerIcon", () => {
  it("returns the deepseek CDN url for the deepseek provider", () => {
    expect(providerIcon("deepseek")).toBe(
      "https://gw.alicdn.com/imgextra/i4/O1CN01YfmXc81ogO3pR0aW8_!!6000000005254-2-tps-400-400.png",
    );
  });

  it("returns the fallback url for an unknown provider", () => {
    expect(providerIcon("unknown-provider")).toBe(FALLBACK);
    expect(providerIcon("")).toBe(FALLBACK);
  });

  it("always returns a non-empty https url for every supported provider", () => {
    const known = ["deepseek", "minions-local", "ollama", "lmstudio"];
    for (const p of known) {
      const url = providerIcon(p);
      expect(url.startsWith("https://")).toBe(true);
      expect(url.length).toBeGreaterThan(0);
      expect(url).not.toBe(FALLBACK);
    }
  });
});
