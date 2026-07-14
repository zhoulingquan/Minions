import { Button, Modal, Input, Form, Divider, Typography, Space } from "antd";
import { Package, Link, FolderOpen, FileArchive, X } from "lucide-react";
import type { useInstallModal } from "../hooks/useInstallModal";
import styles from "./InstallPluginModal.module.less";

const { Text } = Typography;

type InstallModalProps = ReturnType<typeof useInstallModal>;

export function InstallPluginModal({
  installOpen,
  closeModal,
  localInstalling,
  urlInstalling,
  localSel,
  clearSelection,
  dragOver,
  form,
  fileInputRef,
  browseZip,
  handleZipPicked,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  handleInstallLocal,
  handleInstallUrl,
}: Omit<InstallModalProps, "openModal">) {

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept=".zip"
        style={{ display: "none" }}
        onChange={handleZipPicked}
      />

      <Modal
        open={installOpen}
        title={
          <Space>
            <Package size={18} />
            {"安装插件"}
          </Space>
        }
        onCancel={closeModal}
        footer={null}
        destroyOnHidden
        centered
        width={480}
      >
        <div style={{ paddingTop: 16 }}>
          {localSel ? (
            <div className={styles.selectionCard}>
              {localSel.kind === "folder" ? (
                <FolderOpen size={18} />
              ) : (
                <FileArchive size={18} />
              )}
              <Text className={styles.selectionName}>{localSel.name}</Text>
              <Button
                type="text"
                size="small"
                icon={<X size={14} />}
                onClick={clearSelection}
              />
            </div>
          ) : (
            <div
              className={`${styles.dropZone} ${
                dragOver ? styles.dropZoneActive : ""
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={browseZip}
            >
              <Package
                size={36}
                strokeWidth={1.2}
                className={styles.dropIcon}
              />
              <Text className={styles.dropPrimary}>
                {"拖入文件夹或 ZIP 文件"}
              </Text>
              <Text type="secondary" className={styles.dropSecondary}>
                {"或点击选择 ZIP 文件"}
              </Text>
            </div>
          )}

          <Button
            type="primary"
            block
            style={{ marginTop: 12 }}
            disabled={!localSel}
            loading={localInstalling}
            onClick={handleInstallLocal}
          >
            {localInstalling
              ? "安装中..."
              : "安装插件"}
          </Button>

          <Divider style={{ margin: "20px 0 16px" }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {"或通过 URL 安装"}
            </Text>
          </Divider>

          <Form form={form} layout="vertical">
            <Form.Item
              name="source"
              style={{ marginBottom: 8 }}
              rules={[{ required: true, message: " " }]}
            >
              <Input
                prefix={
                  <Link
                    size={14}
                    style={{ color: "var(--ant-color-text-quaternary)" }}
                  />
                }
                placeholder={"https://example.com/plugin.zip"}
                allowClear
                onPressEnter={handleInstallUrl}
              />
            </Form.Item>
            <Button block loading={urlInstalling} onClick={handleInstallUrl}>
              {urlInstalling
                ? "安装中..."
                : "从 URL 安装"}
            </Button>
          </Form>

          <Text
            type="secondary"
            style={{ fontSize: 11, display: "block", marginTop: 14 }}
          >
            {"部分插件（如 hook、monkey-patch 类型）安装或卸载后可能需要重启应用才能完全生效。"}
          </Text>
        </div>
      </Modal>
    </>
  );
}
