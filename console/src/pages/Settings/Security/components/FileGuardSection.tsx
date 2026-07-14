import { useState, useEffect, useCallback } from "react";
import {
  Card,
  Button,
  Input,
  Table,
  Popconfirm,
  Tag,
  Switch,
} from "@agentscope-ai/design";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import { Space } from "antd";
import {
  PlusCircleOutlined,
  DeleteOutlined,
  FolderOutlined,
  FileOutlined,
} from "@ant-design/icons";
import api from "../../../../api";
import styles from "../index.module.less";

interface FileGuardSectionProps {
  onSave?: (handlers: {
    save: () => Promise<void>;
    reset: () => void;
    saving: boolean;
  }) => void;
}

export function FileGuardSection({ onSave }: FileGuardSectionProps = {}) {
    const [enabled, setEnabled] = useState(true);
  const [allowPreviewOutsideWorkspace, setAllowPreviewOutsideWorkspace] =
    useState(false);
  const [paths, setPaths] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newPath, setNewPath] = useState("");
  const { message } = useAppMessage();

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getFileGuard();
      setEnabled(data?.enabled ?? true);
      setAllowPreviewOutsideWorkspace(
        data?.allow_preview_outside_workspace ?? false,
      );
      setPaths(data?.paths ?? []);
    } catch {
      message.error("加载文件防护设置失败");
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleToggle = useCallback(
    async (checked: boolean) => {
      setEnabled(checked);
      try {
        await api.updateFileGuard({ enabled: checked });
        message.success("文件防护设置已保存");
      } catch {
        setEnabled(!checked);
        message.error("保存文件防护设置失败");
      }
    },
    [message],
  );

  const handlePreviewToggle = useCallback(
    async (checked: boolean) => {
      setAllowPreviewOutsideWorkspace(checked);
      try {
        await api.updateFileGuard({
          allow_preview_outside_workspace: checked,
        });
        message.success("文件防护设置已保存");
      } catch {
        setAllowPreviewOutsideWorkspace(!checked);
        message.error("保存文件防护设置失败");
      }
    },
    [message],
  );

  const handleAdd = useCallback(() => {
    const trimmed = newPath.trim();
    if (!trimmed) return;
    if (paths.includes(trimmed)) {
      message.warning("该路径已存在");
      return;
    }
    setPaths((prev) => [...prev, trimmed]);
    setNewPath("");
  }, [message, newPath, paths]);

  const handleRemove = useCallback((path: string) => {
    setPaths((prev) => prev.filter((p) => p !== path));
  }, []);

  const handleSave = useCallback(async () => {
    try {
      setSaving(true);
      await api.updateFileGuard({ paths });
      message.success("文件防护设置已保存");
    } catch {
      message.error("保存文件防护设置失败");
    } finally {
      setSaving(false);
    }
  }, [message, paths]);

  const handleReset = useCallback(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    onSave?.({ save: handleSave, reset: handleReset, saving });
  }, [handleSave, handleReset, saving, onSave]);

  const columns = [
    {
      title: "路径",
      dataIndex: "path",
      key: "path",
      render: (path: string) => {
        const isDir = path.endsWith("/") || path.endsWith("\\");
        return (
          <Space>
            {isDir ? (
              <FolderOutlined style={{ color: "#faad14" }} />
            ) : (
              <FileOutlined style={{ color: "#1890ff" }} />
            )}
            <code>{path}</code>
            {isDir && (
              <Tag color="orange">{"目录"}</Tag>
            )}
          </Space>
        );
      },
    },
    {
      title: "操作",
      key: "actions",
      width: 80,
      render: (_: unknown, record: { path: string }) => (
        <Popconfirm
          title={"从保护列表中移除该路径？"}
          onConfirm={() => handleRemove(record.path)}
          okText={"删除"}
          cancelText={"取消"}
        >
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  const dataSource = paths.map((path) => ({ key: path, path }));

  return (
    <>
      <Card className={styles.formCard}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <span style={{ fontWeight: 500 }}>
            {"启用文件防护"}
          </span>
          <Switch checked={enabled} onChange={handleToggle} />
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <div>
            <span style={{ fontWeight: 500 }}>
              {"允许控制台预览工作区外文件"}
            </span>
            <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>
              {"允许在控制台中预览工作区目录之外的文件，敏感文件防护仍然生效。"}
            </div>
          </div>
          <Switch
            checked={allowPreviewOutsideWorkspace}
            onChange={handlePreviewToggle}
          />
        </div>

        <Space.Compact style={{ width: "100%" }}>
          <Input
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
            placeholder={"输入文件或目录路径（如 ~/.ssh/ 或 /etc/passwd）"}
            onPressEnter={handleAdd}
            allowClear
            disabled={!enabled}
          />
          <Button
            type="primary"
            icon={<PlusCircleOutlined />}
            onClick={handleAdd}
            disabled={!newPath.trim() || !enabled}
          >
            {"添加"}
          </Button>
        </Space.Compact>
      </Card>

      <Card className={styles.tableCard}>
        <Table
          columns={columns}
          dataSource={dataSource}
          loading={loading}
          pagination={false}
          size="middle"
          locale={{
            emptyText: "未配置自定义敏感路径",
          }}
        />
      </Card>
    </>
  );
}
