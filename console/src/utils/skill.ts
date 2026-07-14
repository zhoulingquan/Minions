import type { SkillSyncStatus } from "../api/types";

// ─── Source / Built-in helpers ────────────────────────────────────────────────

export const getSkillDisplaySource = (source: string) =>
  source === "builtin" ? "builtin" : "customized";

export const isSkillBuiltin = (source?: string): boolean =>
  source === "builtin" ||
  (source?.startsWith("builtin:") ?? false) ||
  source === "system";

// ─── Global skills sync-status helpers ─────────────────────────────────────────────────

export const getGlobalBuiltinStatusLabel = (
  status: SkillSyncStatus | "" | undefined,
) => {
  switch (status) {
    case "synced":
      return "最新";
    case "outdated":
      return "已过期";
    case "not_synced":
      return "未同步";
    case "conflict":
      return "冲突";
    default:
      return "-";
  }
};

export const getGlobalBuiltinStatusTone = (
  status: SkillSyncStatus | "" | undefined,
) => {
  switch (status) {
    case "outdated":
      return "outdated";
    case "synced":
      return "synced";
    default:
      return "neutral";
  }
};

// ─── Install-origin helpers ────────────────────────────────────

export const INSTALLED_FROM_LABELS: Record<string, string> = {
  "skills-sh": "skills.sh",
  github: "GitHub",
  lobehub: "LobeHub",
  modelscope: "ModelScope",
  aliyun: "Aliyun",
  skillsmp: "SkillsMP",
  clawhub: "ClawHub",
  url: "URL",
  zip: "ZIP",
};

// Skills without a recorded origin (builtins, hand-created, legacy entries)
// have an empty installed_from and render as an empty string.
export const deriveInstalledFromLabel = (
  installed_from: string | undefined,
): string => {
  if (!installed_from) return "";
  return INSTALLED_FROM_LABELS[installed_from] ?? installed_from;
};
