import { Button, Checkbox } from "@agentscope-ai/design";
import { CheckOutlined, CloudDownloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import type { GlobalSkillSpec } from "../../../../api/types";
import {
  getGlobalBuiltinStatusLabel,
  getGlobalBuiltinStatusTone,
  isSkillBuiltin,
} from "@/utils/skill";
import { SkillVisual } from "@/components/SkillVisual";
import styles from "../index.module.less";
dayjs.extend(relativeTime);

interface GlobalSkillListItemProps {
  skill: GlobalSkillSpec;
  /** Whether the current agent already has this skill installed. */
  isAdded?: boolean;
  /** Quick-add (download into current agent) callback. */
  onAdd?: () => void;
  adding?: boolean;
  /** Batch-mode props. */
  isSelected?: boolean;
  batchModeEnabled?: boolean;
  onToggleSelect?: (name: string) => void;
  /** Click row to edit. */
  onEdit?: (skill: GlobalSkillSpec) => void;
  /** Per-row config-to-agent. */
  onConfigToAgent?: (skill: GlobalSkillSpec) => void;
  /** Per-row delete. */
  onDelete?: (skill: GlobalSkillSpec) => void;
}

export function GlobalSkillListItem({
  skill,
  isAdded,
  onAdd,
  adding,
  isSelected,
  batchModeEnabled,
  onToggleSelect,
  onEdit,
  onConfigToAgent,
  onDelete,
}: GlobalSkillListItemProps) {
  const isBuiltin = isSkillBuiltin(skill.source);

  return (
    <div
      className={`${styles.skillListItem} ${
        isSelected ? styles.selectedListItem : ""
      }`}
      onClick={() => {
        if (batchModeEnabled && onToggleSelect) {
          onToggleSelect(skill.name);
        } else if (onEdit) {
          onEdit(skill);
        }
      }}
    >
      {batchModeEnabled && (
        <Checkbox
          checked={isSelected}
          onClick={(e) => {
            e.stopPropagation();
            onToggleSelect?.(skill.name);
          }}
        />
      )}
      <div className={styles.listItemLeft}>
        <span className={styles.fileIcon}>
          <SkillVisual
            name={skill.name}
            emoji={skill.emoji}
            emojiClassName={styles.skillEmoji}
          />
        </span>
        <div className={styles.listItemInfo}>
          <div className={styles.listItemHeader}>
            <span className={styles.skillTitle}>{skill.name}</span>
            <span className={styles.typeBadge}>
              {isBuiltin ? "内置" : skill.external ? "外部" : "自定义"}
            </span>
            <span
              className={`${styles.statusValue} ${
                styles[getGlobalBuiltinStatusTone(skill.sync_status)]
              }`}
            >
              {getGlobalBuiltinStatusLabel(skill.sync_status)}
            </span>
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
        {onConfigToAgent && (
          <Button
            className={styles.actionButton}
            disabled={batchModeEnabled}
            onClick={(e) => {
              e.stopPropagation();
              onConfigToAgent(skill);
            }}
          >
            {"配置到智能体"}
          </Button>
        )}
        {onDelete && (
          <Button
            danger
            className={styles.deleteButton}
            disabled={batchModeEnabled}
            onClick={(e) => {
              e.stopPropagation();
              void onDelete(skill);
            }}
          >
            {"删除"}
          </Button>
        )}
        {/* Quick-add to current agent (GlobalSkillsTab exclusive) */}
        {onAdd && !isAdded && (
          <Button
            type="primary"
            size="small"
            icon={<CloudDownloadOutlined />}
            loading={adding}
            disabled={adding || batchModeEnabled}
            onClick={(e) => {
              e.stopPropagation();
              onAdd();
            }}
          >
            添加到智能体
          </Button>
        )}
        {isAdded && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "4px 12px",
              borderRadius: 6,
              backgroundColor: "rgba(82, 196, 26, 0.12)",
              color: "#389e0d",
              fontSize: 13,
              fontWeight: 500,
              whiteSpace: "nowrap",
            }}
          >
            <CheckOutlined />
            已添加
          </span>
        )}
      </div>
    </div>
  );
}
