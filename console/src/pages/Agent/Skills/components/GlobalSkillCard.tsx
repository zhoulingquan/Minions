import { useEffect, useState } from "react";
import { Card, Button, Checkbox, Tooltip } from "@agentscope-ai/design";
import {
  CheckOutlined,
  CloudDownloadOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import type { GlobalSkillSpec } from "../../../../api/types";
import {
  getGlobalBuiltinStatusLabel,
  getGlobalBuiltinStatusTone,
  isSkillBuiltin,
} from "@/utils/skill";
import { SkillVisual } from "@/components/SkillVisual";
import styles from "../index.module.less";

interface GlobalSkillCardProps {
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
  /** Click card to edit. */
  onEdit?: (skill: GlobalSkillSpec) => void;
  /** Per-card config-to-agent. */
  onConfigToAgent?: (skill: GlobalSkillSpec) => void;
  /** Per-card delete. */
  onDelete?: (skill: GlobalSkillSpec) => void;
  /** Toggle auto-update sync. */
  onToggleAutoUpdate?: (
    skill: GlobalSkillSpec,
    enabled: boolean,
    targets?: string[] | null,
  ) => void | Promise<void>;
}

export const GlobalSkillCard = ({
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
  onToggleAutoUpdate,
}: GlobalSkillCardProps) => {
  const [isHover, setIsHover] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const syncTone = getGlobalBuiltinStatusTone(skill.sync_status);
  const isBuiltin = isSkillBuiltin(skill.source);
  const hasFooterActions = onConfigToAgent || onDelete || onToggleAutoUpdate;

  useEffect(() => {
    const mql = window.matchMedia("(max-width: 768px)");
    const handleChange = (event: MediaQueryListEvent | MediaQueryList) => {
      setIsMobile(event.matches);
    };
    handleChange(mql);
    mql.addEventListener("change", handleChange);
    return () => {
      mql.removeEventListener("change", handleChange);
    };
  }, []);

  const handleCardClick = () => {
    if (batchModeEnabled && onToggleSelect) {
      onToggleSelect(skill.name);
    } else if (onEdit) {
      onEdit(skill);
    }
  };

  const showFooter =
    hasFooterActions || onAdd || isHover || batchModeEnabled || isMobile;

  return (
    <Card
      hoverable
      className={`${styles.skillCard} ${isSelected ? styles.selectedCard : ""}`}
      onMouseEnter={() => setIsHover(true)}
      onMouseLeave={() => setIsHover(false)}
      onClick={handleCardClick}
      style={{ cursor: onEdit || batchModeEnabled ? "pointer" : "default" }}
    >
      {/* Top row: Icon (left) + Status badge + Checkbox (right) */}
      <div className={styles.cardTopRow}>
        <span className={styles.fileIcon}>
          <SkillVisual
            name={skill.name}
            emoji={skill.emoji}
            emojiClassName={styles.skillEmoji}
          />
        </span>
        <div className={styles.cardTopRight}>
          <span
            className={`${styles.statusBadge} ${styles[`status_${syncTone}`]}`}
          >
            <span className={styles.statusDot} />
            {getGlobalBuiltinStatusLabel(skill.sync_status)}
          </span>
          {batchModeEnabled && (
            <Checkbox
              checked={isSelected}
              onClick={(e) => {
                e.stopPropagation();
                onToggleSelect?.(skill.name);
              }}
            />
          )}
        </div>
      </div>

      {/* Title + Built-in/Custom tag + auto-sync tag */}
      <div className={styles.titleRow}>
        <Tooltip title={skill.name}>
          <h3 className={styles.skillTitle}>
            {skill.name}{" "}
            {isBuiltin ? (
              <span className={styles.builtinTag}>{"内置"}</span>
            ) : (
              <span className={styles.customTag}>{"自定义"}</span>
            )}
            {skill.auto_update && (
              <Tooltip
                title={"已开启自动同步；内容变更会自动同步到关联的智能体。"}
              >
                <span className={styles.autoUpdateTag}>{"自动同步"}</span>
              </Tooltip>
            )}
          </h3>
        </Tooltip>
      </div>

      {/* Updated row */}
      {skill.last_updated && (
        <div className={styles.metaInfoRow}>
          <span className={styles.metaInfoLabel}>{"更新时间"}</span>
          <span className={styles.metaInfoValue}>
            {dayjs(skill.last_updated).fromNow()}
          </span>
        </div>
      )}

      {/* Description */}
      <div className={styles.descriptionSection}>
        <p className={styles.descriptionText}>{skill.description || "-"}</p>
      </div>

      {/* Footer - show on hover, batch mode, or mobile */}
      {showFooter && (
        <div className={styles.cardFooter}>
          {onToggleAutoUpdate && (
            <Tooltip
              title={
                skill.auto_update
                  ? "关闭该技能的自动同步。"
                  : "开启自动同步：内容变更后推送到已安装该技能的智能体。"
              }
            >
              <Button
                className={styles.autoUpdateButton}
                type={skill.auto_update ? "primary" : "default"}
                icon={<SyncOutlined />}
                aria-label={skill.auto_update ? "关闭自动同步" : "开启自动同步"}
                disabled={batchModeEnabled}
                onClick={(e) => {
                  e.stopPropagation();
                  void onToggleAutoUpdate(
                    skill,
                    !skill.auto_update,
                    skill.auto_update_targets ?? null,
                  );
                }}
              />
            </Tooltip>
          )}
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
              className={styles.actionButton}
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
              className={styles.statusValue}
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
              }}
            >
              <CheckOutlined />
              已添加
            </span>
          )}
        </div>
      )}
    </Card>
  );
};
