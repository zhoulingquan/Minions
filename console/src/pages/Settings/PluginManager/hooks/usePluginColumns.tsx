import { Tag, Tooltip, Button, Space, Typography } from "antd";
import { Package, Trash2, CheckCircle, XCircle } from "lucide-react";
import type { PluginType, PluginInfo } from "@/api/modules/plugin";
import { PluginTypeTag } from "../components/PluginTypeTag";

const { Text } = Typography;

interface UsePluginColumnsOptions {
  uninstallingId: string | null;
  onUninstall: (record: PluginInfo) => void;
}

export function usePluginColumns({
  uninstallingId,
  onUninstall,
}: UsePluginColumnsOptions) {

  return [
    {
      title: "插件管理",
      dataIndex: "name",
      key: "name",
      render: (name: string, record: PluginInfo) => (
        <Space direction="vertical" size={2}>
          <Space size={8}>
            <Package size={16} style={{ flexShrink: 0 }} />
            <Text strong>{name}</Text>
          </Space>
          {record.description && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {record.description}
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: "类型",
      dataIndex: "plugin_type",
      key: "plugin_type",
      width: 110,
      render: (type: PluginType) => <PluginTypeTag type={type ?? "general"} />,
    },
    {
      title: "版本",
      dataIndex: "version",
      key: "version",
      width: 100,
      render: (version: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {version}
        </Text>
      ),
    },
    {
      title: "作者",
      dataIndex: "author",
      key: "author",
      width: 140,
      render: (author: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {author || "未知"}
        </Text>
      ),
    },
    {
      title: "Status",
      dataIndex: "loaded",
      key: "loaded",
      width: 110,
      render: (loaded: boolean) =>
        loaded ? (
          <Tag
            icon={<CheckCircle size={12} />}
            color="success"
            style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
          >
            {"运行中"}
          </Tag>
        ) : (
          <Tag
            icon={<XCircle size={12} />}
            color="default"
            style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
          >
            {"未加载"}
          </Tag>
        ),
    },
    {
      title: "",
      key: "actions",
      width: 100,
      render: (_: unknown, record: PluginInfo) => (
        <Tooltip title={"卸载"}>
          <Button
            type="text"
            danger
            size="small"
            icon={<Trash2 size={14} />}
            loading={uninstallingId === record.id}
            onClick={() => onUninstall(record)}
          />
        </Tooltip>
      ),
    },
  ];
}
