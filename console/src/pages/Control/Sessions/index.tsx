import { useEffect, useState, useDeferredValue } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Form, Modal, Table, Button } from "@agentscope-ai/design";
import { useAppMessage } from "../../../hooks/useAppMessage";
import {
  createColumns,
  FilterBar,
  SessionDrawer,
  formatTime,
  type Session,
} from "./components";
import { useSessions } from "./useSessions";
import api from "../../../api";
import { PageHeader } from "@/components/PageHeader";
import { ChannelIcon } from "../Channels/components";
import styles from "./index.module.less";

function SessionsPage() {
    const navigate = useNavigate();
  const {
    sessions,
    loading,
    updateSession,
    deleteSession,
    batchDeleteSessions,
  } = useSessions();
  const [filteredSessions, setFilteredSessions] = useState<Session[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingSession, setEditingSession] = useState<Session | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<Session>();

  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  // Filter states
  const [filterUserId, setFilterUserId] = useState<string>("");
  const [filterChannel, setFilterChannel] = useState<string>("");
  const [filterTitle, setFilterTitle] = useState<string>("");
  const [availableChannels, setAvailableChannels] = useState<string[]>([]);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // ponytail: defer re-filtering until idle to avoid per-keystroke lag
  //   ceiling: if list is 10k+ sessions, consider virtualisation + backend search
  const deferredTitle = useDeferredValue(filterTitle);

  const { message } = useAppMessage();

  useEffect(() => {
    const fetchChannelTypes = async () => {
      try {
        const types = await api.listChannelTypes();
        setAvailableChannels(types);
      } catch (error) {
        console.error("❌ Failed to load channel types:", error);
      }
    };
    fetchChannelTypes();
  }, []);

  // Filter effect
  useEffect(() => {
    let filtered: Session[] = sessions;

    if (filterUserId) {
      filtered = filtered.filter(
        (session: Session) =>
          session.user_id?.toLowerCase().includes(filterUserId.toLowerCase()),
      );
    }

    if (filterChannel) {
      filtered = filtered.filter(
        (session: Session) => session.channel === filterChannel,
      );
    }

    if (deferredTitle) {
      filtered = filtered.filter((session: Session) => {
        const name = session.name || "";
        return name.toLowerCase().includes(deferredTitle.toLowerCase());
      });
    }

    setFilteredSessions(filtered);
  }, [sessions, filterUserId, filterChannel, deferredTitle]);

  const handleEdit = (session: Session) => {
    setEditingSession(session);
    form.setFieldsValue(session as Parameters<typeof form.setFieldsValue>[0]);
    setDrawerOpen(true);
  };

  const handleDelete = (sessionId: string) => {
    Modal.confirm({
      title: "确认删除",
      content: "确定要删除此会话吗？",
      okText: "删除",
      okType: "primary",
      cancelText: "取消",
      onOk: async () => {
        await deleteSession(sessionId);
      },
    });
  };

  const handleView = (session: Session) => {
    navigate(`/chat/${encodeURIComponent(session.id)}`);
  };

  const handleBatchDelete = () => {
    if (selectedRowKeys.length === 0) {
      message.warning("请先选择要删除的会话");
      return;
    }

    Modal.confirm({
      title: "确认删除",
      content: `确定要删除选中的 ${selectedRowKeys.length} 个会话吗？`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        const success = await batchDeleteSessions(selectedRowKeys as string[]);
        if (success) {
          setSelectedRowKeys([]);
        }
      },
    });
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setEditingSession(null);
  };

  const handleSubmit = async (values: Session) => {
    if (editingSession) {
      setSaving(true);
      try {
        const updated = {
          name: values.name,
        };
        const success = await updateSession(editingSession.id, updated);
        if (success) {
          setDrawerOpen(false);
        }
      } finally {
        setSaving(false);
      }
    }
  };

  const columns = createColumns({
    onEdit: handleEdit,
    onDelete: handleDelete,
    onView: handleView,
  });

  const rowSelection = {
    fixed: true,
    columnWidth: 50,
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys);
    },
  };

  return (
    <div className={styles.sessionsPage}>
      <PageHeader
        items={[{ title: "控制" }, { title: "会话" }]}
        extra={
          <div className={styles.headerRight}>
            <FilterBar
              isMobile={isMobile}
              filterUserId={filterUserId}
              filterChannel={filterChannel}
              filterTitle={filterTitle}
              uniqueChannels={availableChannels}
              onUserIdChange={setFilterUserId}
              onChannelChange={setFilterChannel}
              onTitleChange={setFilterTitle}
            />
            {selectedRowKeys.length > 0 && (
              <Button type="primary" danger onClick={handleBatchDelete}>
                {"批量删除"} ({selectedRowKeys.length})
              </Button>
            )}
          </div>
        }
      />

      {isMobile ? (
        <div className={styles.mobileCardList}>
          {filteredSessions.map((session) => (
            <Card
              key={session.id}
              className={styles.mobileSessionCard}
              size="small"
              bodyStyle={{ padding: 24 }}
            >
              <div className={styles.mobileSessionHeader}>
                <span className={styles.mobileSessionName}>
                  {session.name || session.id}
                </span>
                <span className={styles.mobileSessionChannel}>
                  <ChannelIcon channelKey={session.channel} size={24} />
                </span>
              </div>
              <div className={styles.mobileSessionMeta}>
                <span>ID: {session.id}</span>
                {session.user_id && <span>User: {session.user_id}</span>}
                <span>Created: {formatTime(session.created_at)}</span>
              </div>
              <div className={styles.mobileSessionActions}>
                <Button
                  size="small"
                  className={styles.mobileActionBtn}
                  onClick={() => handleEdit(session)}
                >
                  {"编辑"}
                </Button>
                <Button
                  size="small"
                  className={styles.mobileActionBtn}
                  onClick={() => handleView(session)}
                >
                  {"查看"}
                </Button>
                <Button
                  size="small"
                  className={styles.mobileActionBtn}
                  danger
                  onClick={() => handleDelete(session.id)}
                >
                  {"删除"}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className={styles.tableCard} bodyStyle={{ padding: 0 }}>
          <Table
            columns={columns}
            dataSource={filteredSessions}
            loading={loading}
            rowKey="id"
            rowSelection={rowSelection}
            rowClassName={(record) =>
              selectedRowKeys.includes(record.id) ? styles.selectedRow : ""
            }
            scroll={{ x: 1500 }}
            pagination={{
              pageSize: 10,
              showSizeChanger: false,
            }}
          />
        </Card>
      )}

      <SessionDrawer
        open={drawerOpen}
        editingSession={editingSession}
        form={form}
        saving={saving}
        onClose={handleDrawerClose}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

export default SessionsPage;
