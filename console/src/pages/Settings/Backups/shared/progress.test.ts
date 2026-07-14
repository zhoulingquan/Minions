import { describe, it, expect } from "vitest";
import type { BackupProgressEvent } from "@/api/types/backup";
import { handleBackupProgressEvent } from "./progress";

describe("handleBackupProgressEvent", () => {
  it("maps start to progress 0 + starting key", () => {
    const result = handleBackupProgressEvent(
      { type: "start", total_agents: 3, percent: 0 },
    );
    expect(result).toEqual({ progress: 0, msg: "正在初始化备份..." });
  });

  it("maps agent to event.percent and increments index by 1", () => {
    const event: BackupProgressEvent = {
      type: "agent",
      agent_id: "a1",
      index: 2,
      total: 5,
      percent: 40,
    };
    const result = handleBackupProgressEvent(event);
    expect(result.progress).toBe(40);
    expect(result.msg).toBe('正在备份第 3 / 5 个 Agent...');
  });

  it("maps saving to event.percent + saving key", () => {
    const result = handleBackupProgressEvent(
      { type: "saving", percent: 80 },
    );
    expect(result).toEqual({ progress: 80, msg: "正在写入备份文件..." });
  });

  it("maps done to progress 100 + done key", () => {
    const result = handleBackupProgressEvent(
      { type: "done", percent: 100, meta: {} as any },
    );
    expect(result).toEqual({ progress: 100, msg: "备份完成" });
  });

  it("returns empty msg and progress 0 for unknown event types", () => {
    const result = handleBackupProgressEvent(
      { type: "error", message: "boom" } as unknown as BackupProgressEvent,
    );
    expect(result).toEqual({ progress: 0, msg: "" });
  });
});
