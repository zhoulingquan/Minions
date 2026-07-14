/**
 * Renders a row of Ant Design Tags summarising what a backup covers:
 * agent count, global config, skill pool, and secrets (highlighted in orange).
 * Used in the BackupTable scope column and potentially elsewhere.
 */
import { Tag } from "antd";
import type { BackupMeta } from "@/api/types/backup";
import styles from "./ScopeTags.module.less";

interface Props {
  scope: BackupMeta["scope"];
  agentCount?: number;
  compact?: boolean;
}

export default function ScopeTags({ scope, agentCount, compact }: Props) {
    const tagClass = compact ? styles.compactTag : undefined;
  return (
    <div className={styles.scopeTags}>
      {scope.include_agents && agentCount ? (
        <Tag className={tagClass}>
          {`${agentCount} 个 Agent`}
        </Tag>
      ) : null}
      {scope.include_global_config && (
        <Tag className={tagClass}>{"全局设置"}</Tag>
      )}
      {scope.include_global_skills && (
        <Tag className={tagClass}>{"全局技能"}</Tag>
      )}
      {scope.include_secrets && (
        <Tag className={tagClass} color="warning">
          {"密钥"}
        </Tag>
      )}
    </div>
  );
}
