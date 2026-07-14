import { useState, useEffect, useCallback } from "react";
import {
  Card,
  Button,
  Input,
  Table,
  Popconfirm,
  Tag,
  Alert,
} from "@agentscope-ai/design";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import { Space } from "antd";
import { Shield, Plus, Trash2, AlertTriangle } from "lucide-react";
import api from "../../../../api";
import styles from "../index.module.less";

interface AllowNoAuthHostsTabProps {
  onSave?: (handlers: {
    save: () => Promise<void>;
    reset: () => void;
    saving: boolean;
  }) => void;
}

export function AllowNoAuthHostsTab({ onSave }: AllowNoAuthHostsTabProps = {}) {
    const [hosts, setHosts] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newHost, setNewHost] = useState("");
  const { message } = useAppMessage();

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getAllowNoAuthHosts();
      setHosts(data?.hosts ?? ["127.0.0.1", "::1"]);
    } catch {
      message.error("加载免认证主机白名单设置失败");
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const isValidIP = (ip: string): boolean => {
    // IPv4 validation
    const ipv4Regex =
      /^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;

    // IPv6 validation - comprehensive regex supporting compressed notation
    // Matches: full format, compressed (::), leading/trailing compression
    const ipv6Regex =
      /^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]+|::(ffff(:0{1,4})?:)?((25[0-5]|(2[0-4]|1?[0-9])?[0-9])\.){3}(25[0-5]|(2[0-4]|1?[0-9])?[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1?[0-9])?[0-9])\.){3}(25[0-5]|(2[0-4]|1?[0-9])?[0-9]))$/;

    return ipv4Regex.test(ip) || ipv6Regex.test(ip);
  };

  const handleAdd = useCallback(() => {
    const trimmed = newHost.trim();
    if (!trimmed) return;

    if (!isValidIP(trimmed)) {
      message.error("无效的 IP 地址格式");
      return;
    }

    if (hosts.includes(trimmed)) {
      message.warning("该 IP 地址已存在");
      return;
    }

    setHosts((prev) => [...prev, trimmed]);
    setNewHost("");
  }, [newHost, hosts, message]);

  const handleRemove = useCallback((host: string) => {
    setHosts((prev) => prev.filter((h) => h !== host));
  }, []);

  const handleSave = useCallback(async () => {
    try {
      setSaving(true);
      await api.updateAllowNoAuthHosts({ hosts });
      message.success("免认证主机白名单设置已保存");
    } catch {
      message.error("保存免认证主机白名单设置失败");
    } finally {
      setSaving(false);
    }
  }, [hosts, message]);

  const handleReset = useCallback(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    onSave?.({ save: handleSave, reset: handleReset, saving });
  }, [handleSave, handleReset, saving, onSave]);

  const isDefaultHost = (host: string) => {
    return host === "127.0.0.1" || host === "::1";
  };

  const columns = [
    {
      title: "IP 地址",
      dataIndex: "host",
      key: "host",
      render: (host: string) => (
        <Space className={styles.hostRow}>
          <Shield size={16} style={{ color: "#52c41a" }} />
          <code style={{ fontSize: "13px" }}>{host}</code>
          {isDefaultHost(host) && (
            <Tag color="blue">{"默认"}</Tag>
          )}
        </Space>
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 80,
      render: (_: unknown, record: { host: string }) => (
        <Popconfirm
          title={"从白名单中移除该 IP 地址？"}
          onConfirm={() => handleRemove(record.host)}
          okText={"删除"}
          cancelText={"取消"}
        >
          <Button type="text" danger size="small">
            <Trash2 size={14} />
          </Button>
        </Popconfirm>
      ),
    },
  ];

  const dataSource = hosts.map((host) => ({ key: host, host }));

  return (
    <div className={styles.tabContent}>
      <Alert
        message={"安全警告"}
        description={"此列表中的 IP 地址可以无需认证访问 API 端点。默认情况下，本地主机（127.0.0.1 和 ::1）允许 CLI 访问。仅添加可信任的 IP 地址。警告：添加不受信任的 IP 会带来严重的安全风险。"}
        type="warning"
        icon={<AlertTriangle size={16} />}
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Card className={styles.formCard}>
        <Space.Compact style={{ width: "100%" }}>
          <Input
            value={newHost}
            onChange={(e) => setNewHost(e.target.value)}
            placeholder={"输入 IP 地址（例如：192.168.1.100 或 ::1）"}
            onPressEnter={handleAdd}
            allowClear
          />
          <Button
            type="primary"
            icon={<Plus size={16} />}
            onClick={handleAdd}
            disabled={!newHost.trim()}
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
            emptyText: "未配置 IP 地址",
          }}
        />
      </Card>
    </div>
  );
}
