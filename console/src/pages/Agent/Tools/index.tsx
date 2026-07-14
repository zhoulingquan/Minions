import { useEffect, useMemo, useRef, useState } from "react";
import { Spin } from "antd";
import { Empty, Button, Modal, Input, Popconfirm } from "@agentscope-ai/design";
import {
  PlusOutlined,
  DeleteOutlined,
  ReloadOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { useTools } from "./useTools";
import type { ToolInfo } from "../../../api/modules/tools";
import { PageHeader } from "@/components/PageHeader";
import { ToolCard } from "./ToolCard";
import { ToolConfigDrawer } from "./ToolConfigDrawer";
import styles from "./index.module.less";
import channelsStyles from "../../Control/Channels/index.module.less";

type FilterType = "all" | "builtin" | "custom";

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
      title={"新增工具"}
      open={visible}
      onCancel={onClose}
      onOk={handleCreate}
      confirmLoading={saving}
      okButtonProps={{ disabled: !name.trim() || !content }}
      okText={"创建"}
      cancelText={"取消"}
      width={640}
      destroyOnClose
    >
      <div className={styles.toolForm}>
        <div className={styles.formField}>
          <label className={styles.formLabel}>{"选择 .py 文件"}</label>
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
            {"选择文件"}
          </Button>
          {fileName && <span className={styles.fileName}>{fileName}</span>}
        </div>
        <div className={styles.formField}>
          <label className={styles.formLabel}>{"工具名称"}</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={"例如：my_tool"}
          />
        </div>
        {content && (
          <div className={styles.formField}>
            <label className={styles.formLabel}>
              {"工具代码"} ({content.length} chars)
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
  onDelete,
}: {
  visible: boolean;
  toolName: string | null;
  onClose: () => void;
  onLoad: (name: string) => Promise<{ content: string }>;
  onSave: (name: string, content: string) => Promise<void>;
  onReload: (name: string) => Promise<void>;
  onDelete: () => void;
}) {
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
      title={`${"编辑代码"} - ${toolName ?? ""}`}
      open={visible}
      onCancel={onClose}
      footer={
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <Popconfirm
            title={"确定要删除此自定义工具吗？此操作不可撤销。"}
            onConfirm={onDelete}
            okText={"删除"}
            cancelText={"取消"}
            okButtonProps={{ danger: true }}
          >
            <Button danger icon={<DeleteOutlined />}>
              {"删除"}
            </Button>
          </Popconfirm>
          <div style={{ display: "flex", gap: 8 }}>
            <Button onClick={onClose}>{"取消"}</Button>
            <Button
              type="primary"
              loading={saving || loading}
              disabled={loading}
              onClick={handleSave}
            >
              {"保存"}
            </Button>
          </div>
        </div>
      }
      width={720}
      destroyOnClose
    >
      <Spin spinning={loading}>
        <div className={styles.toolForm}>
          <div className={styles.formField}>
            <div className={styles.editHeader}>
              <label className={styles.formLabel}>{"工具代码"}</label>
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={handleReload}
                loading={reloading}
                disabled={loading || !toolName}
              >
                {"重新加载"}
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

export default function ToolsPage() {
  const {
    tools,
    loading,
    customToolNames,
    saveToolConfig,
    loadTools,
    createCustomTool,
    getCustomTool,
    updateCustomTool,
    deleteCustomTool,
    reloadCustomTool,
  } = useTools();
  const [filter, setFilter] = useState<FilterType>("all");
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);
  const [currentTool, setCurrentTool] = useState<ToolInfo | null>(null);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editToolName, setEditToolName] = useState<string | null>(null);

  const handleCardClick = (tool: ToolInfo) => {
    const isCustom = customToolNames.includes(tool.name);
    if (isCustom) {
      setEditToolName(tool.name);
      setEditModalVisible(true);
    } else {
      setCurrentTool(tool);
      setConfigDrawerOpen(true);
    }
  };

  const handleSaveConfig = async (values: Record<string, unknown>) => {
    if (!currentTool) return;
    await saveToolConfig(currentTool.name, values);
    await loadTools();
  };

  const handleDeleteTool = async () => {
    if (!editToolName) return;
    await deleteCustomTool(editToolName);
    setEditModalVisible(false);
    setEditToolName(null);
  };

  // Unified card list: built-in first, then custom (alphabetical);
  // within each group enabled tools come before disabled ones.
  const cards = useMemo(() => {
    const isCustom = (name: string) => customToolNames.includes(name);
    const builtin = tools.filter((tool) => !isCustom(tool.name));
    const custom = tools
      .filter((tool) => isCustom(tool.name))
      .sort((a, b) => a.name.localeCompare(b.name));

    const sortByEnabled = (a: ToolInfo, b: ToolInfo) =>
      Number(b.enabled) - Number(a.enabled);

    let list: ToolInfo[];
    if (filter === "builtin") {
      list = [...builtin].sort(sortByEnabled);
    } else if (filter === "custom") {
      list = [...custom].sort(sortByEnabled);
    } else {
      list = [
        ...builtin.sort(sortByEnabled),
        ...custom.sort(sortByEnabled),
      ];
    }
    return list.map((tool) => ({
      tool,
      isCustom: isCustom(tool.name),
    }));
  }, [tools, customToolNames, filter]);

  const FILTER_TABS: { key: FilterType; label: string }[] = [
    { key: "all", label: "全部" },
    { key: "builtin", label: "内置工具" },
    { key: "custom", label: "自定义工具" },
  ];

  return (
    <div className={channelsStyles.channelsPage}>
      <PageHeader
        className={channelsStyles.pageHeader}
        items={[{ title: "工作区" }, { title: "工具" }]}
        center={
          <div className={channelsStyles.filterTabs}>
            {FILTER_TABS.map(({ key, label }) => (
              <button
                key={key}
                className={`${channelsStyles.filterTab} ${
                  filter === key ? channelsStyles.filterTabActive : ""
                }`}
                onClick={() => setFilter(key)}
              >
                {label}
              </button>
            ))}
          </div>
        }
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddModalVisible(true)}
          >
            {"新增工具"}
          </Button>
        }
      />
      <div className={channelsStyles.channelsContainer}>
        {loading ? (
          <div className={channelsStyles.loading}>
            <span className={channelsStyles.loadingText}>
              {"加载中..."}
            </span>
          </div>
        ) : cards.length === 0 ? (
          <Empty description={"暂无工具配置"} />
        ) : (
          <div className={channelsStyles.channelsGrid}>
            {cards.map(({ tool, isCustom }) => (
              <ToolCard
                key={tool.name}
                tool={tool}
                isCustom={isCustom}
                onClick={() => handleCardClick(tool)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Built-in tool config drawer */}
      <ToolConfigDrawer
        tool={currentTool}
        open={configDrawerOpen}
        onClose={() => setConfigDrawerOpen(false)}
        onSave={handleSaveConfig}
      />

      {/* Add custom tool modal */}
      <AddToolModal
        visible={addModalVisible}
        onClose={() => setAddModalVisible(false)}
        onCreate={createCustomTool}
      />

      {/* Edit custom tool modal */}
      {editToolName && (
        <EditToolModal
          key={editToolName}
          visible={editModalVisible}
          toolName={editToolName}
          onClose={() => {
            setEditModalVisible(false);
            setEditToolName(null);
          }}
          onLoad={getCustomTool}
          onSave={updateCustomTool}
          onReload={reloadCustomTool}
          onDelete={handleDeleteTool}
        />
      )}
    </div>
  );
}
