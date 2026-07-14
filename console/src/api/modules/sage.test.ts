import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../request", () => ({ request: vi.fn() }));

import { request } from "../request";
import { sageApi } from "./sage";

describe("sageApi review and growth endpoints", () => {
  beforeEach(() => vi.mocked(request).mockResolvedValue(undefined));
  afterEach(() => vi.clearAllMocks());

  it("reviews a case without accepting tenant or reviewer identity", async () => {
    await sageApi.reviewSageCase("agent-a", "case-1", "success", "Useful lesson");
    expect(request).toHaveBeenCalledWith("/sage/cases/case-1/review", {
      method: "POST",
      headers: { "X-Agent-Id": "agent-a" },
      body: JSON.stringify({
        outcome: "success",
        decision_summary: "Useful lesson",
        outcome_metrics: {},
      }),
    });
  });

  it("activates an approved insight through the governed action endpoint", async () => {
    await sageApi.actOnSageInsight("agent-a", "insight-1", "activate");
    expect(request).toHaveBeenCalledWith(
      "/sage/insights/insight-1/activate",
      { method: "POST", headers: { "X-Agent-Id": "agent-a" } },
    );
  });
});
