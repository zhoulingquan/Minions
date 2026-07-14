import { memo } from "react";
import { Button, Modal, Tooltip } from "@agentscope-ai/design";
import { CloseOutlined, DownloadOutlined } from "@ant-design/icons";
import { Progress } from "antd";
import type {
  LocalDownloadProgress,
  LocalServerStatus,
} from "../../../../../../api/types";
import styles from "../../../index.module.less";
import {
  formatProgressText,
  getProgressPercent,
  isDownloadActive,
} from "./shared";

interface LocalRuntimePanelProps {
  serverStatus: LocalServerStatus | null;
  hasUpdate: boolean;
  progress: LocalDownloadProgress | null;
  onStart: () => void;
  onCancel: () => void;
  onStop: () => void;
  stopping: boolean;
}

export const LocalRuntimePanel = memo(function LocalRuntimePanel({
  serverStatus,
  hasUpdate,
  progress,
  onStart,
  onCancel,
}: LocalRuntimePanelProps) {
    const installable = serverStatus?.installable ?? true;
  const installed = Boolean(serverStatus?.installed);
  const isDownloading = isDownloadActive(progress);
  const isCanceling = progress?.status === "canceling";
  const isRunning = Boolean(serverStatus?.model_name);
  const showFooterHint = installed || isDownloading;
  const installBadge = hasUpdate
    ? {
        className: styles.localStatusBadgeInstalled,
        label: "可更新",
      }
    : installed
    ? {
        className: styles.localStatusBadgeInstalled,
        label: "已安装",
      }
    : !installable
    ? {
        className: styles.localStatusBadgeDead,
        label: "当前环境不支持",
      }
    : {
        className: styles.localStatusBadgeMuted,
        label: "未安装",
      };
  const runBadge =
    serverStatus?.message && !serverStatus.available
      ? {
          className: styles.localStatusBadgeDead,
          label: "不可用",
        }
      : isRunning
      ? {
          className: styles.localStatusBadgeRunning,
          label: "运行中",
        }
      : {
          className: styles.localStatusBadgeDead,
          label: "不可用",
        };
  const progressPercent = getProgressPercent(progress);
  const progressText = isDownloading ? formatProgressText(progress) : null;
  const canTriggerUpdate = hasUpdate && !isDownloading;

  const handleConfirmUpdate = () => {
    Modal.confirm({
      title: "确认更新 llama.cpp",
      content: isRunning
        ? `更新会覆盖当前已安装的 llama.cpp 版本，并关闭当前正在运行的模型服务（${serverStatus?.model_name ?? "推理引擎"}）。确认后将开始下载并安装最新版本。`
        : "更新会覆盖当前已安装的 llama.cpp 版本。确认后将开始下载并安装最新版本。",
      okText: "确认",
      cancelText: "取消",
      onOk: onStart,
    });
  };

  return (
    <div className={styles.localRuntimePanel}>
      <div className={styles.localRuntimePanelHeader}>
        <div className={styles.modelListItemInfo}>
          <span className={styles.modelListItemName}>
            {"推理引擎"}
          </span>
          <span className={styles.modelListItemId}>
            {"Powered by Llama.cpp"}
          </span>
        </div>
      </div>

      <div className={styles.localSectionNotice}>
        {"默认使用 CPU，如需 GPU 加速功能，请使用 Ollama 或 LM Studio"}
      </div>

      <div className={styles.localEngineStatusRow}>
        <div className={styles.localEngineStatusItem}>
          <span className={styles.localEngineMetricLabel}>
            {"安装"}
          </span>
          {canTriggerUpdate ? (
            <Tooltip title={"点击下载最新版本"}>
              <button
                type="button"
                className={`${styles.localStatusBadge} ${styles.localStatusBadgeAction} ${styles.localStatusBadgeButton}`}
                onClick={handleConfirmUpdate}
              >
                {installBadge.label}
              </button>
            </Tooltip>
          ) : !installable && serverStatus?.message ? (
            <Tooltip title={serverStatus.message}>
              <span
                className={`${styles.localStatusBadge} ${installBadge.className}`}
              >
                {installBadge.label}
              </span>
            </Tooltip>
          ) : (
            <span
              className={`${styles.localStatusBadge} ${installBadge.className}`}
            >
              {installBadge.label}
            </span>
          )}
        </div>
        <div className={styles.localEngineStatusItem}>
          <span className={styles.localEngineMetricLabel}>
            {"状态"}
          </span>
          {serverStatus?.message && !serverStatus.available ? (
            <Tooltip title={serverStatus.message}>
              <span
                className={`${styles.localStatusBadge} ${runBadge.className}`}
              >
                {runBadge.label}
              </span>
            </Tooltip>
          ) : isRunning && serverStatus?.model_name ? (
            <div className={styles.localEngineStatusValue}>
              <span
                className={`${styles.localStatusBadge} ${runBadge.className}`}
              >
                {runBadge.label}
              </span>
            </div>
          ) : (
            <span
              className={`${styles.localStatusBadge} ${runBadge.className}`}
            >
              {runBadge.label}
            </span>
          )}
        </div>
      </div>

      <div className={styles.localStatusCardFooter}>
        <div className={styles.localStatusFooterContent}>
          {showFooterHint ? (
            <span className={styles.localStatusHint}>
              {isDownloading
                ? "您可以离开此页面，下载将在后台继续进行。"
                : "请在下方列表中下载并启动合适的模型"}
            </span>
          ) : null}
          {!isDownloading && !installed ? (
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={onStart}
              disabled={!installable}
            >
              {"安装 llama.cpp"}
            </Button>
          ) : null}
        </div>
      </div>

      {isDownloading ? (
        <div className={styles.localRuntimeDownloadRow}>
          <div className={styles.localRuntimeProgressBlock}>
            <div className={styles.localRuntimeProgressBarRow}>
              <Progress
                className={styles.localRuntimeProgress}
                percent={progressPercent ?? 0}
                showInfo={false}
                status="active"
                strokeColor="#ff7f16"
                strokeWidth={10}
              />
              <Tooltip title={"取消下载"}>
                <Button
                  danger
                  size="small"
                  icon={<CloseOutlined />}
                  loading={isCanceling}
                  disabled={isCanceling}
                  onClick={onCancel}
                />
              </Tooltip>
            </div>
            {progressText ? (
              <span className={styles.localRuntimeProgressMeta}>
                {progressText}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
});
