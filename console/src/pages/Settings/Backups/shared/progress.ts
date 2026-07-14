/**
 * Pure helper that converts raw SSE backup progress events into UI state
 * (percent + status message). Kept separate from the React component so any
 * hook can consume it without importing a component tree.
 */
import type { BackupProgressEvent } from "@/api/types/backup";

/**
 * Maps a single SSE event to { progress (0-100), msg }.
 * Called by useBackupRunner on every streamed chunk.
 */
export function handleBackupProgressEvent(
  event: BackupProgressEvent,
): { progress: number; msg: string } {
  switch (event.type) {
    case "start":
      return { progress: 0, msg: "正在初始化备份..." };
    case "agent":
      return {
        progress: event.percent,
        msg: `正在备份第 ${event.index + 1} / ${event.total} 个 Agent...`,
      };
    case "saving":
      return { progress: event.percent, msg: "正在写入备份文件..." };
    case "done":
      return { progress: 100, msg: "备份完成" };
    default:
      return { progress: 0, msg: "" };
  }
}
