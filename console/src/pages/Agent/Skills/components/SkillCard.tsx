import React, { useEffect, useState } from "react";
import { Card, Button, Checkbox, Switch, Tooltip } from "@agentscope-ai/design";
import {
  CalendarFilled,
  FileTextFilled,
  FileZipFilled,
  FilePdfFilled,
  FileWordFilled,
  FileExcelFilled,
  FilePptFilled,
  FileImageFilled,
  CodeFilled,
  CloudUploadOutlined,
  CloudDownloadOutlined,
  LinkOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import type { SkillSpec } from "../../../../api/types";
import styles from "../index.module.less";
import {
  getWorkspaceSyncAction,
  getWorkspaceSyncActionHint,
  getWorkspaceSyncActionLabel,
  getWorkspaceSyncLabel,
  getWorkspaceSyncTone,
} from "./skillSync";

interface SkillCardProps {
  skill: SkillSpec;
  selected?: boolean;
  onSelect?: (e: React.MouseEvent) => void;
  onClick: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  onToggleEnabled: () => void | Promise<void>;
  onDelete?: (e?: React.MouseEvent) => void;
  onSync?: () => void;
  syncing?: boolean;
}

const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth <= 768 : false,
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return isMobile;
};

const normalizeSkillIconKey = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .split(/\s+/)[0]
    ?.replace(/[^a-z0-9_-]/g, "") || "";

export const getFileIcon = (filePath: string) => {
  const skillKey = normalizeSkillIconKey(filePath);
  const textSkillIcons = new Set([
    "news",
    "file_reader",
    "browser_visible",
    "guidance",
    "himalaya",
    "dingtalk_channel",
  ]);

  if (textSkillIcons.has(skillKey)) {
    return <FileTextFilled style={{ color: "#1890ff" }} />;
  }

  switch (skillKey) {
    case "docx":
      return <FileWordFilled style={{ color: "#2B8DFF" }} />;
    case "xlsx":
      return <FileExcelFilled style={{ color: "#44C161" }} />;
    case "pptx":
      return <FilePptFilled style={{ color: "#FF5B3B" }} />;
    case "pdf":
      return <FilePdfFilled style={{ color: "#F04B57" }} />;
    case "cron":
      return <CalendarFilled style={{ color: "#13c2c2" }} />;
    default:
      break;
  }

  const extension = filePath.split(".").pop()?.toLowerCase() || "";

  switch (extension) {
    case "txt":
    case "md":
    case "markdown":
      return <FileTextFilled style={{ color: "#1890ff" }} />;
    case "zip":
    case "rar":
    case "7z":
    case "tar":
    case "gz":
      return <FileZipFilled style={{ color: "#fa8c16" }} />;
    case "pdf":
      return <FilePdfFilled style={{ color: "#F04B57" }} />;
    case "doc":
    case "docx":
      return <FileWordFilled style={{ color: "#2B8DFF" }} />;
    case "xls":
    case "xlsx":
      return <FileExcelFilled style={{ color: "#44C161" }} />;
    case "ppt":
    case "pptx":
      return <FilePptFilled style={{ color: "#FF5B3B" }} />;
    case "jpg":
    case "jpeg":
    case "png":
    case "gif":
    case "svg":
    case "webp":
      return <FileImageFilled style={{ color: "#eb2f96" }} />;
    case "py":
    case "js":
    case "ts":
    case "jsx":
    case "tsx":
    case "java":
    case "cpp":
    case "c":
    case "go":
    case "rs":
    case "rb":
    case "php":
      return <CodeFilled style={{ color: "#52c41a" }} />;
    default:
      return <FileTextFilled style={{ color: "#1890ff" }} />;
  }
};

export const getSkillVisual = (name: string, emoji?: string) => {
  if (emoji) {
    return <span className={styles.skillEmoji}>{emoji}</span>;
  }
  return getFileIcon(name);
};

export const SkillCard = React.memo(function SkillCard({
  skill,
  selected,
  onSelect,
  onClick,
  onMouseEnter,
  onMouseLeave,
  onToggleEnabled,
  onDelete,
  onSync,
  syncing = false,
}: SkillCardProps) {
  const batchMode = selected !== undefined;
  const [isHover, setIsHover] = useState(false);
  const isMobile = useIsMobile();

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete?.(e);
  };

  const handleSelectClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect?.(e);
  };

  const handleCardClick = (e: React.MouseEvent) => {
    if (batchMode && onSelect) {
      onSelect(e);
    } else {
      onClick();
    }
  };

  const isBuiltin =
    skill.source === "builtin" ||
    skill.source?.startsWith("builtin:") ||
    skill.source === "system";
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
    <Card
      hoverable
      onClick={handleCardClick}
      onMouseEnter={() => {
        setIsHover(true);
        onMouseEnter?.();
      }}
      onMouseLeave={() => {
        setIsHover(false);
        onMouseLeave?.();
      }}
      className={`${styles.skillCard} ${selected ? styles.selectedCard : ""}`}
      style={{ cursor: "pointer" }}
    >
      {/* Top row: Icon (left) + Status badge + Checkbox (right) */}
      <div className={styles.cardTopRow}>
        <span className={styles.fileIcon}>
          {getSkillVisual(skill.name, skill.emoji)}
        </span>
        <div className={styles.cardTopRight}>
          <Tooltip title={skill.enabled ? "禁用技能" : "启用技能"}>
            <span
              className={styles.skillEnableSwitch}
              onClick={(event) => event.stopPropagation()}
            >
              <Switch
                size="small"
                checked={Boolean(skill.enabled)}
                disabled={batchMode}
                aria-label={`启用技能 ${skill.name}`}
                onChange={() => void onToggleEnabled()}
              />
            </span>
          </Tooltip>
          {batchMode && (
            <Checkbox checked={selected} onClick={handleSelectClick} />
          )}
        </div>
      </div>

      {/* Title + Built-in/Custom tag */}
      <div className={styles.titleRow}>
        <Tooltip title={skill.name}>
          <h3 className={styles.skillTitle}>
            {skill.name}{" "}
            {isBuiltin ? (
              <span className={styles.builtinTag}>{"内置"}</span>
            ) : (
              <span className={styles.customTag}>{"自定义"}</span>
            )}
            {syncLabel && (
              <span
                className={`${styles.workspaceSyncTag} ${
                  styles[`workspaceSync_${syncTone}`]
                }`}
              >
                {syncLabel}
              </span>
            )}
          </h3>
        </Tooltip>
      </div>

      {/* Channels row */}
      <div className={styles.metaInfoRow}>
        <span className={styles.metaInfoLabel}>{"适用频道"}</span>
        <span className={styles.metaInfoValue}>
          {(skill.channels || ["all"])
            .map((ch) => (ch === "all" ? "所有" : ch))
            .join(", ")}
        </span>
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

      {onSync && syncAction && (
        <div
          className={`${styles.workspaceSyncActionRow} ${
            styles[`workspaceSyncAction_${syncTone}`]
          }`}
        >
          <span className={styles.workspaceSyncActionHint}>
            {getWorkspaceSyncActionHint(skill)}
          </span>
          <Button
            type={syncAction === "resolve" ? "default" : "primary"}
            danger={skill.sync_status === "conflict"}
            size="small"
            className={styles.workspaceSyncActionButton}
            disabled={batchMode}
            loading={syncing}
            icon={syncActionIcon}
            onClick={(e) => {
              e.stopPropagation();
              onSync();
            }}
          >
            {getWorkspaceSyncActionLabel(skill)}
          </Button>
        </div>
      )}

      {/* Delete remains a secondary hover action; enablement lives in the switch. */}
      {onDelete && (isHover || batchMode || isMobile) && (
        <div
          className={`${styles.cardFooter} ${
            syncAction ? styles.cardFooterWithSyncAction : ""
          }`}
        >
          <Button
            danger
            className={styles.deleteButton}
            disabled={batchMode}
            onClick={handleDeleteClick}
          >
            {"删除"}
          </Button>
        </div>
      )}
    </Card>
  );
});
