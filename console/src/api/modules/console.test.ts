import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../request", () => ({
  request: vi.fn(),
}));

import { consoleApi } from "./console";
import { request } from "../request";

describe("consoleApi", () => {
  beforeEach(() => {
    vi.mocked(request).mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("getPushMessages without sessionId calls GET /console/push-messages", async () => {
    const data = { messages: [], pending_approvals: [] };
    vi.mocked(request).mockResolvedValue(data);
    const result = await consoleApi.getPushMessages();
    expect(request).toHaveBeenCalledWith("/console/push-messages");
    expect(result).toEqual(data);
  });

  it("getPushMessages with sessionId appends session_id query", async () => {
    const data = { messages: [], pending_approvals: [] };
    vi.mocked(request).mockResolvedValue(data);
    const result = await consoleApi.getPushMessages("sess-1");
    expect(request).toHaveBeenCalledWith(
      "/console/push-messages?session_id=sess-1",
    );
    expect(result).toEqual(data);
  });

  it("getMsgEvents builds ordered query string with multiple params", async () => {
    const data = { events: [] };
    vi.mocked(request).mockResolvedValue(data);
    const result = await consoleApi.getMsgEvents({
      limit: 200,
      offset: 10,
      source_type: "cron",
      unread_only: true,
    });
    expect(request).toHaveBeenCalledWith(
      "/console/msg/events?limit=200&offset=10&source_type=cron&unread_only=true",
    );
    expect(result).toEqual(data);
  });

  it("getMsgEvents without params calls GET without query", async () => {
    const data = { events: [] };
    vi.mocked(request).mockResolvedValue(data);
    await consoleApi.getMsgEvents();
    expect(request).toHaveBeenCalledWith("/console/msg/events");
  });

  it("markMsgRead posts payload body (event_ids and all variants)", async () => {
    // event_ids variant
    const resp1 = { updated: 1 };
    vi.mocked(request).mockResolvedValue(resp1);
    const r1 = await consoleApi.markMsgRead({ event_ids: ["e1", "e2"] });
    expect(request).toHaveBeenCalledWith("/console/msg/read", {
      method: "POST",
      body: JSON.stringify({ event_ids: ["e1", "e2"] }),
    });
    expect(r1).toEqual(resp1);

    // all variant
    const resp2 = { updated: 5 };
    vi.mocked(request).mockResolvedValue(resp2);
    const r2 = await consoleApi.markMsgRead({ all: true });
    expect(request).toHaveBeenCalledWith("/console/msg/read", {
      method: "POST",
      body: JSON.stringify({ all: true }),
    });
    expect(r2).toEqual(resp2);
  });

  it("deleteMsgEvent URL-encodes eventId (slash handled)", async () => {
    const resp = { deleted: true, trace_deleted: false, run_id: null };
    vi.mocked(request).mockResolvedValue(resp);
    const result = await consoleApi.deleteMsgEvent("a/b");
    expect(request).toHaveBeenCalledWith("/console/msg/events/a%2Fb", {
      method: "DELETE",
    });
    expect(result).toEqual(resp);
  });

  it("getMsgTrace URL-encodes runId", async () => {
    const trace = {
      run_id: "r/1",
      created_at: 0,
      completed_at: null,
      status: "ok",
      meta: {},
      events: [],
    };
    vi.mocked(request).mockResolvedValue(trace);
    const result = await consoleApi.getMsgTrace("r/1");
    expect(request).toHaveBeenCalledWith("/console/msg/traces/r%2F1");
    expect(result).toEqual(trace);
  });
});
