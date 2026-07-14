import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Drawer,
  Table,
  Button,
  Space,
  Tooltip,
  Typography,
  Select,
  Popconfirm,
} from "antd";
import {
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import {
  accessControlApi,
  type PendingEntry,
} from "../../../../api/modules/accessControl";
import { getChannelLabel, type ChannelKey } from "./constants";
import { ChannelIcon } from "./ChannelIcon";

const { Text } = Typography;

type PendingAction = "approve" | "deny" | "dismiss";

const ACTION_API_MAP: Record<
  PendingAction,
  typeof accessControlApi.approveAclPending
> = {
  approve: accessControlApi.approveAclPending,
  deny: accessControlApi.denyAclPending,
  dismiss: accessControlApi.dismissAclPending,
};

const ACTION_SUCCESS_LABELS: Record<PendingAction, string> = {
  approve: "已加入白名单",
  deny: "已加入黑名单",
  dismiss: "已忽略",
};

interface PendingApprovalsDrawerProps {
  open: boolean;
  onClose: () => void;
}

export function PendingApprovalsDrawer({
  open,
  onClose,
}: PendingApprovalsDrawerProps) {
    const { message } = useAppMessage();
  const [pending, setPending] = useState<PendingEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);

  const fetchPending = useCallback(async () => {
    setLoading(true);
    try {
      const data = await accessControlApi.getAclAllPending();
      setPending(data);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      fetchPending();
      setSelectedRowKeys([]);
    }
  }, [open, fetchPending]);

  const availableChannels = useMemo(() => {
    const channelSet = new Set(pending.map((entry) => entry.channel));
    return Array.from(channelSet);
  }, [pending]);

  const filteredPending = useMemo(() => {
    if (selectedChannels.length === 0) return pending;
    return pending.filter((entry) => selectedChannels.includes(entry.channel));
  }, [pending, selectedChannels]);

  const selectedEntries = useMemo(
    () =>
      selectedRowKeys.map((key) => {
        const [channel, ...rest] = key.split(":");
        return { channel, user_id: rest.join(":") };
      }),
    [selectedRowKeys],
  );

  const handleRemarkSave = async (entry: PendingEntry, remark: string) => {
    try {
      await accessControlApi.updatePendingRemark(
        entry.channel,
        entry.user_id,
        remark,
      );
      setPending((prev) =>
        prev.map((p) =>
          p.channel === entry.channel && p.user_id === entry.user_id
            ? { ...p, remark }
            : p,
        ),
      );
    } catch {
      message.error("操作失败");
    }
  };

  const handleUsernameSave = async (entry: PendingEntry, username: string) => {
    try {
      await accessControlApi.updateUsername(
        entry.channel,
        entry.user_id,
        username,
      );
      setPending((prev) =>
        prev.map((p) =>
          p.channel === entry.channel && p.user_id === entry.user_id
            ? { ...p, username }
            : p,
        ),
      );
    } catch {
      message.error("操作失败");
    }
  };

  const handleAction = async (entry: PendingEntry, action: PendingAction) => {
    const key = `${entry.channel}:${entry.user_id}`;
    setActionLoading(key);
    try {
      await ACTION_API_MAP[action]([
        { channel: entry.channel, user_id: entry.user_id },
      ]);
      message.success(ACTION_SUCCESS_LABELS[action]);
      await fetchPending();
    } catch {
      message.error("操作失败");
    } finally {
      setActionLoading(null);
    }
  };

  const handleBatchAction = async (action: PendingAction) => {
    setBatchLoading(true);
    try {
      await ACTION_API_MAP[action](selectedEntries);
      message.success(
        `已成功处理 ${selectedEntries.length} 位用户`,
      );
      setSelectedRowKeys([]);
      await fetchPending();
    } catch {
      message.error("操作失败");
    } finally {
      setBatchLoading(false);
    }
  };

  const columns = [
    {
      title: "频道",
      dataIndex: "channel",
      key: "channel",
      width: 100,
      fixed: "left" as const,
      render: (channel: string) => (
        <Tooltip title={getChannelLabel(channel as ChannelKey)}>
          <Space size={4}>
            <ChannelIcon channelKey={channel as ChannelKey} size={16} />
            <span>{getChannelLabel(channel as ChannelKey)}</span>
          </Space>
        </Tooltip>
      ),
    },
    {
      title: "用户名",
      dataIndex: "username",
      key: "username",
      width: 120,
      render: (username: string, record: PendingEntry) => (
        <Text
          editable={{
            onChange: (value) => handleUsernameSave(record, value),
            text: username || "",
          }}
        >
          {username || <span style={{ color: "#bbb" }}>-</span>}
        </Text>
      ),
    },
    {
      title: "用户 ID",
      dataIndex: "user_id",
      key: "user_id",
      width: 160,
      ellipsis: { showTitle: false },
      render: (userId: string) => (
        <Space size={4}>
          <Text ellipsis={{ tooltip: userId }} style={{ maxWidth: 120 }}>
            {userId}
          </Text>
          <Text copyable={{ text: userId }} />
        </Space>
      ),
    },
    {
      title: "首条消息",
      dataIndex: "first_message",
      key: "first_message",
      width: 160,
      ellipsis: true,
      render: (msg: string) => (
        <Tooltip title={msg}>
          <span>{msg || "-"}</span>
        </Tooltip>
      ),
    },
    {
      title: "备注",
      dataIndex: "remark",
      key: "remark",
      width: 130,
      render: (remark: string, record: PendingEntry) => (
        <Text
          editable={{
            onChange: (value) => handleRemarkSave(record, value),
            text: remark || "",
          }}
        >
          {remark || <span style={{ color: "#bbb" }}>-</span>}
        </Text>
      ),
    },
    {
      title: "时间",
      dataIndex: "timestamp",
      key: "timestamp",
      width: 150,
      render: (ts: number) => (ts ? new Date(ts * 1000).toLocaleString() : "-"),
    },
    {
      title: "操作",
      key: "actions",
      width: 200,
      fixed: "right" as const,
      render: (_: unknown, record: PendingEntry) => {
        const key = `${record.channel}:${record.user_id}`;
        const isLoading = actionLoading === key;
        return (
          <Space size={0}>
            <Button
              type="text"
              size="small"
              loading={isLoading}
              onClick={() => handleAction(record, "approve")}
              style={{ color: "#52c41a", padding: "0 4px" }}
            >
              {"加入白名单"}
            </Button>
            <Button
              type="text"
              size="small"
              danger
              loading={isLoading}
              onClick={() => handleAction(record, "deny")}
              style={{ padding: "0 4px" }}
            >
              {"加入黑名单"}
            </Button>
            <Button
              type="text"
              size="small"
              loading={isLoading}
              onClick={() => handleAction(record, "dismiss")}
              style={{ padding: "0 4px" }}
            >
              {"忽略"}
            </Button>
          </Space>
        );
      },
    },
  ];

  const hasSelection = selectedRowKeys.length > 0;

  return (
    <Drawer
      width={920}
      title={"待审批"}
      open={open}
      onClose={onClose}
      destroyOnHidden
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
        }}
      >
        <Select
          mode="multiple"
          allowClear
          placeholder={"按渠道筛选"}
          value={selectedChannels}
          onChange={(values) => {
            setSelectedChannels(values);
            setSelectedRowKeys([]);
          }}
          style={{ minWidth: 200 }}
          options={availableChannels.map((ch) => ({
            label: getChannelLabel(ch as ChannelKey),
            value: ch,
          }))}
        />
        <Space>
          {hasSelection && (
            <Text type="secondary" style={{ fontSize: 13 }}>
              {`已选 ${selectedRowKeys.length} 项`}
            </Text>
          )}
          <Popconfirm
            title={`确认通过 ${selectedRowKeys.length} 位用户？`}
            onConfirm={() => handleBatchAction("approve")}
            disabled={!hasSelection}
          >
            <Button
              type="primary"
              size="small"
              icon={<CheckOutlined />}
              disabled={!hasSelection}
              loading={batchLoading}
            >
              {"批量通过"}
            </Button>
          </Popconfirm>
          <Popconfirm
            title={`确认将 ${selectedRowKeys.length} 位用户加入黑名单？`}
            onConfirm={() => handleBatchAction("deny")}
            disabled={!hasSelection}
          >
            <Button
              size="small"
              icon={<CloseOutlined />}
              disabled={!hasSelection}
              loading={batchLoading}
            >
              {"批量拉黑"}
            </Button>
          </Popconfirm>
          <Popconfirm
            title={`确认忽略 ${selectedRowKeys.length} 位用户？`}
            onConfirm={() => handleBatchAction("dismiss")}
            disabled={!hasSelection}
          >
            <Button
              danger
              size="small"
              icon={<DeleteOutlined />}
              disabled={!hasSelection}
              loading={batchLoading}
            >
              {"批量忽略"}
            </Button>
          </Popconfirm>
        </Space>
      </div>

      <Table
        dataSource={filteredPending}
        columns={columns}
        rowKey={(r) => `${r.channel}:${r.user_id}`}
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys as string[]),
        }}
        size="small"
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        scroll={{ x: 1050 }}
        locale={{
          emptyText: (
            <div style={{ padding: "48px 0" }}>
              {"暂无待审批"}
            </div>
          ),
        }}
      />
    </Drawer>
  );
}
