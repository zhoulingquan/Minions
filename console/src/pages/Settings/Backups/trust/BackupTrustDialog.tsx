import { Alert, Modal } from "antd";

/**
 * Shared confirmation for backups that do not verify with the local signing
 * key. Import and restore both use this dialog so the trust decision is
 * explicit before the backend accepts or signs a foreign/legacy archive.
 */
interface Props {
  open: boolean;
  mode: "foreign" | "legacy";
  backupName?: string;
  confirmLoading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function BackupTrustDialog({
  open,
  mode,
  backupName,
  confirmLoading,
  onConfirm,
  onCancel,
}: Props) {
    const isLegacy = mode === "legacy";

  return (
    <Modal
      title={
        isLegacy
          ? "信任历史备份？"
          : "信任此备份？"
      }
      open={open}
      onOk={onConfirm}
      onCancel={onCancel}
      confirmLoading={confirmLoading}
      okButtonProps={{ danger: true }}
      okText={"确认"}
      cancelText={"取消"}
      centered
    >
      <Alert
        type="warning"
        showIcon
        message={
          backupName ||
          "备份归档"
        }
        description={
          isLegacy
            ? "此旧版备份没有本地签名。仅在信任来源时继续；确认后会使用当前实例签名再恢复。"
            : "此备份不是由当前实例签名。仅在信任来源时继续；恢复时默认保留本地安全和 MCP 配置。"
        }
      />
    </Modal>
  );
}
