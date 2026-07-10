import { useEffect, useMemo, useRef, useState } from "react";
import { Spin } from "antd";
import {
  Card,
  Empty,
  Button,
  Modal,
  Input,
  Popconfirm,
} from "@agentscope-ai/design";
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  ReloadOutlined,
  UploadOutlined,
  EyeInvisibleOutlined,
} from "@ant-design/icons";
import { useCustomTools } from "./useCustomTools";
import { useTranslation } from "react-i18next";
import type { ToolInfo } from "../../../api/modules/tools";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

const ICON_PALETTE = [
  "#f56a00",
  "#7265e6",
  "#ffbf00",
  "#00a2ae",
  "#87d068",
  "#1890ff",
  "#eb2f96",
  "#722ed1",
];

function hashStringToIndex(value: string, mod: number): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % mod;
}

function ToolIcon({ icon, name }: { icon: string; name: string }) {
  if (icon) {
    return <span>{icon}</span>;
  }
  const letter = name.charAt(0).toUpperCase();
  const backgroundColor =
    ICON_PALETTE[hashStringToIndex(name, ICON_PALETTE.length)];
  return (
    <span className={styles.toolIconFallback} style={{ backgroundColor }}>
      {letter}
    </span>
  );
}

/** Modal for creating a custom tool by uploading a .py file. */
function AddToolModal({
  visible,
  onClose,
  onCreate,
}: {
  visible: boolean;
  onClose: () => void;
  onCreate: (name: string, content: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [fileName, setFileName] = useState("");
  const [saving, setSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (visible) {
      setName("");
      setContent("");
      setFileName("");
    }
  }, [visible]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !file.name.toLowerCase().endsWith(".py")) return;
    setFileName(file.name);
    const stem = file.name.replace(/\.py$/i, "");
    setName(stem);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result;
      if (typeof text === "string") setContent(text);
    };
    reader.readAsText(file);
  };

  const handleCreate = async () => {
    const trimmed = name.trim();
    if (!trimmed || !content) return;
    try {
      setSaving(true);
      await onCreate(trimmed, content);
      onClose();
    } catch (error) {
      console.error("Failed to create custom tool:", error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={t("tools.addTool")}
      open={visible}
      onCancel={onClose}
      onOk={handleCreate}
      confirmLoading={saving}
      okButtonProps={{ disabled: !name.trim() || !content }}
      okText={t("common.create")}
      cancelText={t("common.cancel")}
      width={640}
      destroyOnClose
    >
      <div className={styles.toolForm}>
        <div className={styles.formField}>
          <label className={styles.formLabel}>{t("tools.selectFile")}</label>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".py"
            style={{ display: "none" }}
          />
          <Button
            icon={<UploadOutlined />}
            onClick={() => fileInputRef.current?.click()}
          >
            {t("tools.chooseFile")}
          </Button>
          {fileName && (
            <span className={styles.fileName}>{fileName}</span>
          )}
        </div>
        <div className={styles.formField}>
          <label className={styles.formLabel}>{t("tools.toolName")}</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("tools.toolNamePlaceholder")}
          />
        </div>
        {content && (
          <div className={styles.formField}>
            <label className={styles.formLabel}>
              {t("tools.toolCode")} ({content.length} chars)
            </label>
            <Input.TextArea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={15}
              className={styles.codeEditor}
              spellCheck={false}
            />
          </div>
        )}
      </div>
    </Modal>
  );
}

/** Modal for editing a custom tool's code with reload action. */
function EditToolModal({
  visible,
  toolName,
  onClose,
  onLoad,
  onSave,
  onReload,
}: {
  visible: boolean;
  toolName: string | null;
  onClose: () => void;
  onLoad: (name: string) => Promise<{ content: string }>;
  onSave: (name: string, content: string) => Promise<void>;
  onReload: (name: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reloading, setReloading] = useState(false);

  useEffect(() => {
    if (!visible || !toolName) return;
    setLoading(true);
    setContent("");
    onLoad(toolName)
      .then((data) => setContent(data.content))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [visible, toolName, onLoad]);

  const handleSave = async () => {
    if (!toolName) return;
    try {
      setSaving(true);
      await onSave(toolName, content);
      onClose();
    } catch (error) {
      console.error("Failed to save:", error);
    } finally {
      setSaving(false);
    }
  };

  const handleReload = async () => {
    if (!toolName) return;
    try {
      setReloading(true);
      await onReload(toolName);
    } catch (error) {
      console.error("Failed to reload:", error);
    } finally {
      setReloading(false);
    }
  };

  return (
    <Modal
      title={`${t("tools.editCode")} - ${toolName ?? ""}`}
      open={visible}
      onCancel={onClose}
      onOk={handleSave}
      confirmLoading={saving || loading}
      okButtonProps={{ disabled: loading }}
      okText={t("common.save")}
      cancelText={t("common.cancel")}
      width={720}
      destroyOnClose
    >
      <Spin spinning={loading}>
        <div className={styles.toolForm}>
          <div className={styles.formField}>
            <div className={styles.editHeader}>
              <label className={styles.formLabel}>{t("tools.toolCode")}</label>
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={handleReload}
                loading={reloading}
                disabled={loading || !toolName}
              >
                {t("tools.reload")}
              </Button>
            </div>
            <Input.TextArea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={15}
              className={styles.codeEditor}
              spellCheck={false}
            />
          </div>
        </div>
      </Spin>
    </Modal>
  );
}

export default function CustomToolsPage() {
  const { t } = useTranslation();
  const {
    tools,
    loading,
    toggleEnabled,
    createCustomTool,
    getCustomTool,
    updateCustomTool,
    deleteCustomTool,
    reloadCustomTool,
  } = useCustomTools();
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editToolName, setEditToolName] = useState<string | null>(null);

  const handleEditTool = (tool: ToolInfo) => {
    setEditToolName(tool.name);
    setEditModalVisible(true);
  };

  const handleDeleteTool = async (tool: ToolInfo) => {
    await deleteCustomTool(tool.name);
  };

  const { enabledTools, disabledTools } = useMemo(() => {
    const enabled = tools.filter((tool) => tool.enabled);
    const disabled = tools.filter((tool) => !tool.enabled);
    return { enabledTools: enabled, disabledTools: disabled };
  }, [tools]);

  return (
    <div className={styles.toolsPage}>
      <PageHeader
        items={[
          { title: t("nav.agent") },
          { title: t("nav.customTools") },
        ]}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddModalVisible(true)}
          >
            {t("tools.addTool")}
          </Button>
        }
      />
      <div className={styles.toolsContainer}>
        {loading ? (
          <div className={styles.loading}>
            <p>{t("common.loading")}</p>
          </div>
        ) : tools.length === 0 ? (
          <Empty description={t("tools.emptyState")} />
        ) : (
          <>
            {/* Enabled Section */}
            {enabledTools.length > 0 && (
              <div className={styles.panelSection}>
                <div className={styles.panelTitle}>
                  <span className={styles.panelDotGreen} />
                  {t("common.enabled")}
                  <span className={styles.panelCount}>
                    {enabledTools.length} {t("tools.active")}
                  </span>
                </div>
                <div className={styles.toolsGrid}>
                  {enabledTools.map((tool) => (
                    <Card
                      key={tool.name}
                      className={`${styles.toolCard} ${styles.enabledCard}`}
                    >
                      <div className={styles.cardHeader}>
                        <h3 className={styles.toolName} title={tool.name}>
                          <ToolIcon icon={tool.icon} name={tool.name} />{" "}
                          <span className={styles.toolNameText}>
                            {tool.name}
                          </span>
                        </h3>
                        <div className={styles.statusContainer}>
                          <span className={styles.statusDot} />
                          <span className={styles.statusText}>
                            {t("common.enabled")}
                          </span>
                        </div>
                      </div>

                      <p className={styles.toolDescription}>
                        {tool.description}
                      </p>

                      <div className={styles.cardFooter}>
                        <Button
                          className={styles.toggleButton}
                          onClick={() => handleEditTool(tool)}
                          icon={<EditOutlined />}
                        >
                          {t("tools.editCode")}
                        </Button>
                        <Popconfirm
                          title={t("tools.deleteToolConfirm")}
                          onConfirm={() => handleDeleteTool(tool)}
                          okText={t("common.delete")}
                          cancelText={t("common.cancel")}
                          okButtonProps={{ danger: true }}
                        >
                          <Button
                            className={styles.toggleButton}
                            danger
                            icon={<DeleteOutlined />}
                          >
                            {t("tools.deleteTool")}
                          </Button>
                        </Popconfirm>
                        <Button
                          className={styles.toggleButton}
                          onClick={() => toggleEnabled(tool)}
                          icon={<EyeInvisibleOutlined />}
                        >
                          {t("common.disable")}
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {/* Available Section */}
            {disabledTools.length > 0 && (
              <div className={styles.panelSectionDashed}>
                <div className={styles.panelTitle}>
                  <span className={styles.panelDotGray} />
                  {t("tools.available")}
                </div>
                <div className={styles.availableGrid}>
                  {disabledTools.map((tool) => (
                    <div
                      key={tool.name}
                      className={styles.availableItem}
                      onClick={() => toggleEnabled(tool)}
                    >
                      <ToolIcon icon={tool.icon} name={tool.name} />
                      <span
                        className={styles.availableItemName}
                        title={tool.name}
                      >
                        {tool.name}
                      </span>
                      <span className={styles.availableItemAction}>
                        {t("tools.enableAction")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <AddToolModal
        visible={addModalVisible}
        onClose={() => setAddModalVisible(false)}
        onCreate={createCustomTool}
      />
      {editToolName && (
        <EditToolModal
          key={editToolName}
          visible={editModalVisible}
          toolName={editToolName}
          onClose={() => setEditModalVisible(false)}
          onLoad={getCustomTool}
          onSave={updateCustomTool}
          onReload={reloadCustomTool}
        />
      )}
    </div>
  );
}
