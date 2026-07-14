import { Button, Checkbox, Switch } from "@agentscope-ai/design";
import {
  CloudDownloadOutlined,
  CloudUploadOutlined,
  LinkOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import type { SkillSpec } from "../../../../api/types";
import { isSkillBuiltin } from "@/utils/skill";
import { getSkillVisual } from "./SkillCard";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import styles from "../index.module.less";
import {
  getWorkspaceSyncAction,
  getWorkspaceSyncActionLabel,
  getWorkspaceSyncLabel,
  getWorkspaceSyncTone,
} from "./skillSync";

dayjs.extend(relativeTime);

interface SkillListItemProps {
  skill: SkillSpec;
  batchModeEnabled: boolean;
  isSelected: boolean;
  onSelect: () => void;
  onClick: () => void;
  onToggleEnabled: () => Promise<void>;
  onDelete?: () => void;
  onSync?: () => void;
  syncing?: boolean;
}

export function SkillListItem({
  skill,
  batchModeEnabled,
  isSelected,
  onSelect,
  onClick,
  onToggleEnabled,
  onDelete,
  onSync,
  syncing = false,
}: SkillListItemProps) {
  const isBuiltin = isSkillBuiltin(skill.source);
  const channels = (skill.channels || ["all"])
    .map((ch) => (ch === "all" ? "所有" : ch))
    .join(", ");
  const syncLabel = getWorkspaceSyncLabel(skill.sync_status);
  const syncTone = getWorkspaceSyncTone(skill.sync_status);
  const syncAction = getWorkspaceSyncAction(skill);
  const syncActionIcon =
    syncAction === "pull" ? (
      <CloudDownloadOutlined />
    ) : syncAction === "resolve" ? (
      <WarningOutlined />
    ) : syncAction === "link" ? (
      <LinkOutlined />
    ) : (
      <CloudUploadOutlined />
    );

  return (
    <div
      className={`${styles.skillListItem} ${
        isSelected ? styles.selectedListItem : ""
      }`}
      onClick={() => {
        if (batchModeEnabled) onSelect();
        else onClick();
      }}
    >
      {batchModeEnabled && (
        <Checkbox
          checked={isSelected}
          onClick={(e) => {
            e.stopPropagation();
            onSelect();
          }}
        />
      )}
      <div className={styles.listItemLeft}>
        <span className={styles.fileIcon}>
          {getSkillVisual(skill.name, skill.emoji)}
        </span>
        <div className={styles.listItemInfo}>
          <div className={styles.listItemHeader}>
            <span className={styles.skillTitle}>{skill.name}</span>
            <span className={styles.typeBadge}>
              {isBuiltin ? "内置" : "自定义"}
            </span>
            <span className={styles.channelBadge}>{channels}</span>
            {syncLabel && (
              <span
                className={`${styles.workspaceSyncTag} ${
                  styles[`workspaceSync_${syncTone}`]
                }`}
              >
                {syncLabel}
              </span>
            )}
            {skill.last_updated && (
              <span className={styles.listItemTime}>
                {"更新时间"} {dayjs(skill.last_updated).fromNow()}
              </span>
            )}
          </div>
          <p className={styles.listItemDesc}>{skill.description || "-"}</p>
        </div>
      </div>
      <div className={styles.listItemRight}>
        {onSync && syncAction && (
          <Button
            type={syncAction === "resolve" ? "default" : "primary"}
            danger={skill.sync_status === "conflict"}
            size="small"
            loading={syncing}
            disabled={batchModeEnabled}
            icon={syncActionIcon}
            onClick={(e) => {
              e.stopPropagation();
              onSync();
            }}
          >
            {getWorkspaceSyncActionLabel(skill)}
          </Button>
        )}
        <span onClick={(e) => e.stopPropagation()}>
          <Switch
            checked={skill.enabled}
            disabled={batchModeEnabled}
            onChange={onToggleEnabled}
          />
        </span>
        {onDelete && (
          <Button
            danger
            disabled={batchModeEnabled}
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
          >
            {"删除"}
          </Button>
        )}
      </div>
    </div>
  );
}
