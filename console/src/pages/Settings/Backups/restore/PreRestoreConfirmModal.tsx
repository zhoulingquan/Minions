/**
 * First step in the restore flow: asks the user whether they want to create
 * an automatic snapshot before overwriting data. Three outcomes:
 *   - Cancel     → abort entirely
 *   - No backup  → proceed straight to RestoreBackupModal
 *   - Yes backup → open SilentBackupModal first, then RestoreBackupModal
 */
import { Button, Modal } from "antd";
import type { BackupMeta } from "@/api/types/backup";

interface Props {
  target: BackupMeta | null;
  onCancel: () => void;
  onNoBackup: (target: BackupMeta) => void;
  onYesBackup: (target: BackupMeta) => void;
}

export default function PreRestoreConfirmModal({
  target,
  onCancel,
  onNoBackup,
  onYesBackup,
}: Props) {

  return (
    <Modal
      open={!!target}
      title={"创建恢复前备份"}
      centered
      width={520}
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          {"取消"}
        </Button>,
        <Button key="no" onClick={() => target && onNoBackup(target)}>
          {"否，直接恢复"}
        </Button>,
        <Button
          key="yes"
          type="primary"
          onClick={() => target && onYesBackup(target)}
        >
          {"是，先创建备份"}
        </Button>,
      ]}
    >
      <p style={{ lineHeight: 1.6 }}>{"恢复操作不可逆。是否先创建当前状态的备份？这样如果恢复出现问题，您可以回退到当前状态。"}</p>
    </Modal>
  );
}
