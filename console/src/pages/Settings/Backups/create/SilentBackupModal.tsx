import { useEffect } from "react";
import { Modal } from "antd";
import type { BackupMeta } from "@/api/types/backup";
import { useBackupRunner } from "../shared/useBackupRunner";
import { buildPreRestoreScope } from "../shared/scope";
import BackupProgress from "./BackupProgress";

interface Props {
  /** The backup being restored. When non-null the modal opens and auto-starts. */
  target: BackupMeta | null;
  /** All currently known agent IDs; passed explicitly to buildPreRestoreScope. */
  agentIds: string[];
  onClose: () => void;
  onSuccess: () => void;
}

/**
 * Automatic pre-restore snapshot modal.
 * Opens when target is set, immediately starts a full backup, shows only a
 * progress bar and a Cancel button. No user form input required.
 */
export default function SilentBackupModal({
  target,
  agentIds,
  onClose,
  onSuccess,
}: Props) {
    const runner = useBackupRunner({ onSuccess, onClose });

  useEffect(() => {
    if (!target) return;
    const { name, scope, agents } = buildPreRestoreScope(agentIds);
    runner.start({
      name,
      description: "恢复前自动创建的备份",
      scope,
      agents,
    });
    // runner.start is stable (doesn't change between renders)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  return (
    <Modal
      title={"正在创建恢复前备份..."}
      open={target !== null}
      onCancel={runner.cancel}
      footer={null}
      destroyOnHidden
      centered
      closable={false}
      maskClosable={false}
    >
      <BackupProgress
        progress={runner.progress}
        progressMsg={runner.progressMsg}
      />
    </Modal>
  );
}
