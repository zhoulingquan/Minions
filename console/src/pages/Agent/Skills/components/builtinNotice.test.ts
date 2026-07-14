import { describe, it, expect } from "vitest";
import type { BuiltinUpdateNotice } from "@/api/types";
import { getBuiltinNoticeLines } from "./builtinNotice";

function notice(overrides: Partial<BuiltinUpdateNotice>): BuiltinUpdateNotice {
  return {
    fingerprint: "fp",
    has_updates: true,
    total_changes: 0,
    actionable_skill_names: [],
    added: [],
    missing: [],
    updated: [],
    removed: [],
    ...overrides,
  } as BuiltinUpdateNotice;
}

describe("getBuiltinNoticeLines", () => {
  it("returns [] when notice is null", () => {
    expect(getBuiltinNoticeLines(null)).toEqual([]);
  });

  it("returns [] when has_updates is not true", () => {
    expect(
      getBuiltinNoticeLines(notice({ has_updates: false })),
    ).toEqual([]);
  });

  it("emits one line for the added category only", () => {
    const n = notice({ added: [{ name: "skillA" }, { name: "skillB" }] });
    const lines = getBuiltinNoticeLines(n);
    expect(lines).toEqual(["新增：skillA, skillB"]);
  });

  it("emits one line per non-empty category (added + removed)", () => {
    const n = notice({
      added: [{ name: "skillA" }],
      removed: [{ name: "skillZ" }],
    });
    const lines = getBuiltinNoticeLines(n);
    expect(lines).toEqual([
      "新增：skillA",
      "移除：skillZ",
    ]);
  });

  it("returns [] when every category array is empty (has_updates=true but no changes listed)", () => {
    const n = notice({
      added: [],
      missing: [],
      updated: [],
      removed: [],
    });
    expect(getBuiltinNoticeLines(n)).toEqual([]);
  });

  it("filters out empty/whitespace names so no line is emitted for them", () => {
    const n = notice({
      added: [{ name: "  " }, { name: "" }],
      updated: [{ name: "real" }],
    });
    const lines = getBuiltinNoticeLines(n);
    expect(lines).toEqual(["更新：real"]);
  });
});
