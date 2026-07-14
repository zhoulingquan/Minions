import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
dayjs.extend(relativeTime);

import { formatTimeAgo } from "./utils";

describe("formatTimeAgo", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-06-01T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns a relative time string for a recent timestamp", () => {
    const fiveMinutesAgo = new Date("2024-06-01T11:55:00Z").getTime();
    const result = formatTimeAgo(fiveMinutesAgo);
    expect(result).toBe("5 minutes ago");
  });

  it("returns a relative time string for a string timestamp", () => {
    const result = formatTimeAgo("2024-06-01T11:00:00Z");
    expect(result).toBe("an hour ago");
  });
});
