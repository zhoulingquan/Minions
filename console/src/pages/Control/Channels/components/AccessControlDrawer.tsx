import { useState, useEffect, useCallback } from "react";
import {
  Drawer,
  Tabs,
  Table,
  Button,
  Input,
  Select,
  Modal,
  Popconfirm,
  Space,
  Typography,
} from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import type React from "react";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import {
  accessControlApi,
  type ACLData,
  type ACLUserEntry,
} from "../../../../api/modules/accessControl";
import { getChannelLabel, type ChannelKey } from "./constants";

interface AccessControlDrawerProps {
  open: boolean;
  onClose: () => void;
}

function toEntries(
  map: Record<string, { remark: string; username: string }> | undefined,
): ACLUserEntry[] {
  if (!map) return [];
  return Object.entries(map).map(([userId, info]) => ({
    userId,
    remark: info?.remark ?? "",
    username: info?.username ?? "",
  }));
}

export function AccessControlDrawer({
  open,
  onClose,
}: AccessControlDrawerProps) {
    const { message } = useAppMessage();
  const [allACLs, setAllACLs] = useState<Record<string, ACLData>>({});
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [newUserId, setNewUserId] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [newRemark, setNewRemark] = useState("");
  const [activeTab, setActiveTab] = useState<"whitelist" | "blacklist">(
    "whitelist",
  );
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);

  const fetchACLs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await accessControlApi.getAclAll();
      setAllACLs(data);
      const keys = Object.keys(data);
      if (keys.length === 0) {
        setSelectedChannel(null);
      } else if (!selectedChannel || !keys.includes(selectedChannel)) {
        setSelectedChannel(keys[0]);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [selectedChannel]);

  useEffect(() => {
    if (open) fetchACLs();
  }, [open, fetchACLs]);

  const channelKeys = Object.keys(allACLs);
  const currentACL = selectedChannel ? allACLs[selectedChannel] : null;
  const handleAdd = async () => {
    if (!selectedChannel || !newUserId.trim()) return;
    const addApi =
      activeTab === "whitelist"
        ? accessControlApi.addAclWhitelist
        : accessControlApi.addAclBlacklist;
    try {
      await addApi([
        {
          channel: selectedChannel,
          user_id: newUserId.trim(),
          remark: newRemark.trim(),
          username: newUsername.trim(),
        },
      ]);
      message.success("用户添加成功");
      setNewUserId("");
      setNewUsername("");
      setNewRemark("");
      await fetchACLs();
    } catch {
      message.error("操作失败");
    }
  };

  const handleRemove = async (userId: string) => {
    if (!selectedChannel) return;
    const removeApi =
      activeTab === "whitelist"
        ? accessControlApi.removeAclWhitelist
        : accessControlApi.removeAclBlacklist;
    try {
      await removeApi([{ channel: selectedChannel, user_id: userId }]);
      message.success("用户删除成功");
      await fetchACLs();
    } catch {
      message.error("操作失败");
    }
  };

  const handleRemarkSave = async (userId: string, remark: string) => {
    if (!selectedChannel) return;
    try {
      await accessControlApi.updateAclRemark(selectedChannel, userId, remark);
      setAllACLs((prev) => {
        const channelData = prev[selectedChannel];
        if (!channelData) return prev;
        const list = channelData[activeTab];
        const existing = list[userId] ?? { remark: "", username: "" };
        return {
          ...prev,
          [selectedChannel]: {
            ...channelData,
            [activeTab]: {
              ...list,
              [userId]: { ...existing, remark },
            },
          },
        };
      });
    } catch {
      message.error("操作失败");
    }
  };

  const handleBatchRemove = async () => {
    if (!selectedChannel || selectedRowKeys.length === 0) return;
    setBatchLoading(true);
    const removeApi =
      activeTab === "whitelist"
        ? accessControlApi.removeAclWhitelist
        : accessControlApi.removeAclBlacklist;
    try {
      await removeApi(
        selectedRowKeys.map((userId) => ({
          channel: selectedChannel,
          user_id: userId as string,
        })),
      );
      message.success(
        `已成功处理 ${selectedRowKeys.length} 位用户`,
      );
      setSelectedRowKeys([]);
      await fetchACLs();
    } catch {
      message.error("操作失败");
    } finally {
      setBatchLoading(false);
    }
  };

  const listData: ACLUserEntry[] = currentACL
    ? toEntries(currentACL[activeTab])
    : [];

  const handleUsernameSave = async (userId: string, username: string) => {
    if (!selectedChannel) return;
    try {
      await accessControlApi.updateUsername(selectedChannel, userId, username);
      setAllACLs((prev) => {
        const channelData = prev[selectedChannel];
        if (!channelData) return prev;
        const list = channelData[activeTab];
        const existing = list[userId] ?? { remark: "", username: "" };
        return {
          ...prev,
          [selectedChannel]: {
            ...channelData,
            [activeTab]: {
              ...list,
              [userId]: { ...existing, username },
            },
          },
        };
      });
    } catch {
      message.error("操作失败");
    }
  };

  const columns = [
    {
      title: "用户名",
      dataIndex: "username",
      key: "username",
      width: 120,
      render: (username: string, record: ACLUserEntry) => (
        <Typography.Text
          editable={{
            onChange: (value) => handleUsernameSave(record.userId, value),
            text: username || "",
          }}
        >
          {username || <span style={{ color: "#bbb" }}>-</span>}
        </Typography.Text>
      ),
    },
    {
      title: "用户 ID",
      dataIndex: "userId",
      key: "userId",
      ellipsis: { showTitle: false },
      render: (userId: string) => (
        <Space size={4}>
          <Typography.Text
            ellipsis={{ tooltip: userId }}
            style={{ maxWidth: 180 }}
          >
            {userId}
          </Typography.Text>
          <Typography.Text copyable={{ text: userId }} />
        </Space>
      ),
    },
    {
      title: "备注",
      dataIndex: "remark",
      key: "remark",
      width: 160,
      render: (remark: string, record: ACLUserEntry) => (
        <Typography.Text
          editable={{
            onChange: (value) => handleRemarkSave(record.userId, value),
            text: remark,
          }}
        >
          {remark || <span style={{ color: "#bbb" }}>-</span>}
        </Typography.Text>
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 80,
      render: (_: unknown, record: ACLUserEntry) => (
        <Popconfirm
          title={`Remove ${record.userId}?`}
          onConfirm={() => handleRemove(record.userId)}
        >
          <Button type="text" danger size="small">
            {"删除"}
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Drawer
      width={700}
      title={"访问控制"}
      open={open}
      onClose={onClose}
      destroyOnHidden
    >
      <Tabs
        activeKey={activeTab}
        onChange={(k) => {
          setActiveTab(k as "whitelist" | "blacklist");
          setSelectedRowKeys([]);
        }}
        items={[
          { key: "whitelist", label: "白名单" },
          { key: "blacklist", label: "黑名单" },
        ]}
        tabBarExtraContent={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddModalOpen(true)}
            disabled={!selectedChannel}
          >
            {"添加用户"}
          </Button>
        }
      />

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
        }}
      >
        <Select
          value={selectedChannel}
          onChange={(value) => {
            setSelectedChannel(value);
            setSelectedRowKeys([]);
          }}
          style={{ width: 180 }}
          disabled={channelKeys.length === 0}
          placeholder={"按渠道筛选"}
          options={channelKeys.map((key) => ({
            label: getChannelLabel(key as ChannelKey),
            value: key,
          }))}
        />
        <Space>
          {selectedRowKeys.length > 0 && (
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              {`已选 ${selectedRowKeys.length} 项`}
            </Typography.Text>
          )}
          <Popconfirm
            title={`确认删除 ${selectedRowKeys.length} 位用户？`}
            onConfirm={handleBatchRemove}
            disabled={selectedRowKeys.length === 0}
          >
            <Button
              danger
              size="small"
              icon={<DeleteOutlined />}
              disabled={selectedRowKeys.length === 0}
              loading={batchLoading}
            >
              {"删除"}
            </Button>
          </Popconfirm>
        </Space>
      </div>

      <Table
        dataSource={listData}
        columns={columns}
        rowKey={(record) => record.userId}
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys),
        }}
        size="small"
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        locale={{
          emptyText: (
            <div style={{ padding: "48px 0" }}>
              {activeTab === "whitelist"
                ? "暂无白名单用户"
                : "暂无黑名单用户"}
            </div>
          ),
        }}
      />

      <Modal
        title={"添加用户"}
        open={addModalOpen}
        onCancel={() => {
          setAddModalOpen(false);
          setNewUserId("");
          setNewUsername("");
          setNewRemark("");
        }}
        onOk={async () => {
          await handleAdd();
          setAddModalOpen(false);
        }}
        okButtonProps={{ disabled: !newUserId.trim() }}
        destroyOnHidden
      >
        <Space direction="vertical" style={{ width: "100%" }} size={16}>
          <div>
            <Typography.Text
              strong
              style={{ display: "block", marginBottom: 6 }}
            >
              {"用户 ID"}
            </Typography.Text>
            <Input
              placeholder={"输入用户 ID"}
              value={newUserId}
              onChange={(e) => setNewUserId(e.target.value)}
            />
          </div>
          <div>
            <Typography.Text
              strong
              style={{ display: "block", marginBottom: 6 }}
            >
              {"用户名"}
            </Typography.Text>
            <Input
              placeholder={"输入用户名称（可选）"}
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
            />
          </div>
          <div>
            <Typography.Text
              strong
              style={{ display: "block", marginBottom: 6 }}
            >
              {"备注"}
            </Typography.Text>
            <Input
              placeholder={"输入备注（可选）"}
              value={newRemark}
              onChange={(e) => setNewRemark(e.target.value)}
            />
          </div>
        </Space>
      </Modal>
    </Drawer>
  );
}
