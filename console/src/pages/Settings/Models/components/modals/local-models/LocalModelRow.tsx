import { memo } from "react";
import { Button } from "@agentscope-ai/design";
import {
  DeleteOutlined,
  DownloadOutlined,
  PlayCircleOutlined,
  StopOutlined,
} from "@ant-design/icons";
import type { LocalModelInfo } from "../../../../../../api/types";
import styles from "../../../index.module.less";
import prettyBytes from "pretty-bytes";

interface LocalModelRowProps {
  model: LocalModelInfo;
  currentRunningModelName: string | null;
  isModelDownloading: boolean;
  isServerBusy: boolean;
  startingModelName: string | null;
  stoppingServer: boolean;
  deletingModelName: string | null;
  onStartDownload: (model: LocalModelInfo) => void;
  onStartServer: (model: LocalModelInfo) => void;
  onStopServer: () => void;
  onDeleteModel: (model: LocalModelInfo) => void;
}

export const LocalModelRow = memo(function LocalModelRow({
  model,
  currentRunningModelName,
  isModelDownloading,
  isServerBusy,
  startingModelName,
  stoppingServer,
  deletingModelName,
  onStartDownload,
  onStartServer,
  onStopServer,
  onDeleteModel,
}: LocalModelRowProps) {
    const isRunning = currentRunningModelName === model.id;
  const isStarting = startingModelName === model.id;
  const isDeleting = deletingModelName === model.id;

  return (
    <div className={styles.modelListItem}>
      <div className={styles.modelListItemInfo}>
        <span className={styles.modelListItemName}>{model.name}</span>
        <span className={styles.modelListItemId}>
          {model.id} · {prettyBytes(model.size_bytes)}
        </span>
      </div>
      <div className={styles.modelListItemActions}>
        {!model.downloaded ? (
          <Button
            type="primary"
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => onStartDownload(model)}
            disabled={isModelDownloading || isServerBusy}
          >
            {"下载"}
          </Button>
        ) : isRunning ? (
          <>
            <Button
              danger
              size="small"
              icon={<StopOutlined />}
              loading={stoppingServer}
              onClick={onStopServer}
            >
              {"停止"}
            </Button>
            <Button
              danger
              size="small"
              icon={<DeleteOutlined />}
              loading={isDeleting}
              disabled
              onClick={() => onDeleteModel(model)}
            >
              {"删除"}
            </Button>
          </>
        ) : (
          <>
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              loading={isStarting}
              onClick={() => onStartServer(model)}
              disabled={isServerBusy || isDeleting}
            >
              {"启动"}
            </Button>
            <Button
              danger
              size="small"
              icon={<DeleteOutlined />}
              loading={isDeleting}
              onClick={() => onDeleteModel(model)}
              disabled={isDeleting || isServerBusy}
            >
              {"删除"}
            </Button>
          </>
        )}
      </div>
    </div>
  );
});
