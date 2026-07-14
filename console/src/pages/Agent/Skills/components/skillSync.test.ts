import { describe, expect, it } from "vitest";
import type { SkillSpec } from "../../../../api/types";
import {
  canSyncWorkspaceSkill,
  getWorkspaceSyncAction,
  getWorkspaceSyncActionHint,
  getWorkspaceSyncActionLabel,
  getWorkspaceSyncLabel,
} from "./skillSync";

const skill = (overrides: Partial<SkillSpec>): SkillSpec => ({
  name: "demo",
  content: "content",
  source: "customized",
  ...overrides,
});

describe("workspace skill sync presentation", () => {
  it("offers a visible global push when the agent copy changed", () => {
    const changed = skill({ sync_status: "outdated_agent", in_global: true });
    expect(canSyncWorkspaceSkill(changed)).toBe(true);
    expect(getWorkspaceSyncAction(changed)).toBe("push");
    expect(getWorkspaceSyncLabel(changed.sync_status)).toBe("智能体有改进");
    expect(getWorkspaceSyncActionLabel(changed)).toBe("同步到全局");
  });

  it("uses publish wording for a local-only skill", () => {
    const local = skill({ sync_status: "not_synced", in_global: false });
    expect(getWorkspaceSyncAction(local)).toBe("push");
    expect(getWorkspaceSyncActionLabel(local)).toBe("发布到全局");
  });

  it("offers a pull when only the global copy changed", () => {
    const changed = skill({ sync_status: "outdated_global", in_global: true });
    expect(getWorkspaceSyncAction(changed)).toBe("pull");
    expect(getWorkspaceSyncActionLabel(changed)).toBe("更新智能体");
    expect(getWorkspaceSyncActionHint(changed)).toBe("全局版本有更新");
  });

  it("offers conflict resolution when both copies changed", () => {
    const conflicted = skill({ sync_status: "conflict", in_global: true });
    expect(getWorkspaceSyncAction(conflicted)).toBe("resolve");
    expect(getWorkspaceSyncActionLabel(conflicted)).toBe("处理冲突");
  });

  it("offers a safe link action for identical legacy copies", () => {
    const legacy = skill({
      sync_status: "not_synced",
      in_global: true,
      global_hash: "same-hash",
      agent_hash: "same-hash",
    });
    expect(getWorkspaceSyncAction(legacy)).toBe("link");
    expect(getWorkspaceSyncActionLabel(legacy)).toBe("建立同步");
  });

  it("requires a version choice for different unlinked copies", () => {
    const unlinked = skill({
      sync_status: "not_synced",
      in_global: true,
      global_hash: "global-hash",
      agent_hash: "agent-hash",
    });
    expect(getWorkspaceSyncAction(unlinked)).toBe("resolve");
    expect(getWorkspaceSyncActionLabel(unlinked)).toBe("处理差异");
  });

  it("does not guess a sync action when metadata is unavailable", () => {
    expect(canSyncWorkspaceSkill(skill({}))).toBe(false);
    expect(getWorkspaceSyncAction(skill({}))).toBeNull();
  });
});
