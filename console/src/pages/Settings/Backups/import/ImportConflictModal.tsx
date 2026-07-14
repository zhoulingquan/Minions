/**
 * Shown when importing a zip whose ID already exists in the store (HTTP 409).
 * Presents the conflicting backup's metadata and lets the user choose to
 * replace it or cancel. The resolution is handled by useImportFlow.
 */
import { Button, Modal } from "antd";
import dayjs from "dayjs";
import type { BackupMeta } from "@/api/types/backup";

interface Props {
  conflictMeta: BackupMeta | null;
  onChoice: () => void;
  onCancel: () => void;
}

export default function ImportConflictModal({
  conflictMeta,
  onChoice,
  onCancel,
}: Props) {

  return (
    <Modal
      open={!!conflictMeta}
      title={"备份已存在"}
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          {"取消"}
        </Button>,
        <Button key="replace" type="primary" danger onClick={() => onChoice()}>
          {"覆盖"}
        </Button>,
      ]}
    >
      <p>{"导入的备份与系统中已有的备份 ID 相同，是否覆盖已有备份？"}</p>
      {conflictMeta && (
        <div
          style={{
            background: "var(--ant-color-fill-quaternary)",
            padding: 12,
            borderRadius: 6,
            marginTop: 8,
          }}
        >
          <div>
            <strong>{"名称"}:</strong> {conflictMeta.name}
          </div>
          <div>
            <strong>ID:</strong>{" "}
            <span style={{ fontFamily: "monospace", fontSize: 12 }}>
              {conflictMeta.id}
            </span>
          </div>
          <div>
            <strong>{"创建时间"}:</strong>{" "}
            {dayjs(conflictMeta.created_at).format("YYYY-MM-DD HH:mm:ss")}
          </div>
        </div>
      )}
    </Modal>
  );
}
