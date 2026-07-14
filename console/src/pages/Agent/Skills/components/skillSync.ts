import type { SkillSpec, SkillSyncStatus } from "../../../../api/types";

export type WorkspaceSyncAction = "push" | "pull" | "resolve" | "link";

export function getWorkspaceSyncLabel(status?: SkillSyncStatus): string {
  switch (status) {
    case "synced":
      return "已与全局同步";
    case "outdated_agent":
      return "智能体有改进";
    case "outdated_global":
      return "全局有更新";
    case "conflict":
      return "同步冲突";
    case "not_synced":
      return "未关联全局";
    default:
      return "";
  }
}

export function getWorkspaceSyncTone(
  status?: SkillSyncStatus,
): "synced" | "changed" | "conflict" | "neutral" {
  switch (status) {
    case "synced":
      return "synced";
    case "outdated_agent":
    case "outdated_global":
      return "changed";
    case "conflict":
      return "conflict";
    default:
      return "neutral";
  }
}

export function getWorkspaceSyncAction(
  skill: SkillSpec,
): WorkspaceSyncAction | null {
  switch (skill.sync_status) {
    case "outdated_agent":
      return "push";
    case "outdated_global":
    case "outdated":
      return "pull";
    case "conflict":
      return "resolve";
    case "not_synced":
      if (!skill.in_global) return "push";
      if (
        skill.global_hash &&
        skill.agent_hash &&
        skill.global_hash === skill.agent_hash
      ) {
        return "link";
      }
      return "resolve";
    default:
      return null;
  }
}

export function canSyncWorkspaceSkill(skill: SkillSpec): boolean {
  return getWorkspaceSyncAction(skill) !== null;
}

export function getWorkspaceSyncActionLabel(skill: SkillSpec): string {
  const action = getWorkspaceSyncAction(skill);
  if (action === "pull") return "更新智能体";
  if (action === "resolve") {
    return skill.sync_status === "conflict" ? "处理冲突" : "处理差异";
  }
  if (action === "link") return "建立同步";
  if (action === "push" && !skill.in_global) return "发布到全局";
  if (action === "push") return "同步到全局";
  return "";
}

export function getWorkspaceSyncActionHint(skill: SkillSpec): string {
  const action = getWorkspaceSyncAction(skill);
  if (action === "pull") return "全局版本有更新";
  if (action === "resolve") {
    return skill.sync_status === "conflict"
      ? "智能体与全局版本都已变更"
      : "同名版本内容不同，需要选择保留哪一份";
  }
  if (action === "link") return "内容一致，可建立版本关联";
  if (action === "push" && !skill.in_global) return "仅存在于当前智能体";
  if (action === "push") return "智能体版本有改进";
  return "";
}
