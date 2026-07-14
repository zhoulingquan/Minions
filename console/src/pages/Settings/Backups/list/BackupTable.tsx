/**
 * Renders the paginated backup list with inline Restore / Export / Delete actions.
 * Accepts the full backup list and a searchQuery; filtering is done in-component
 * via useMemo so the parent doesn't need to maintain a filtered copy.
 *
 * Export shows a danger-confirmation modal before downloading the zip.
 * Delete calls the API directly and triggers onRefresh on success.
 * Restore delegates to the parent via onRestore (handled by useRestoreFlow).
 */
import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Empty,
  Modal,
  Pagination,
  Popconfirm,
  Table,
  Tooltip,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import api from "@/api";
import { useAppMessage } from "@/hooks/useAppMessage";
import type { BackupMeta } from "@/api/types/backup";
import ScopeTags from "./ScopeTags";
import styles from "./BackupTable.module.less";

dayjs.extend(relativeTime);

// Backups are created manually, so total count stays low (typically < 100).
// Loading all at once and paginating client-side avoids backend complexity.
const PAGE_SIZE = 10;

interface Props {
  backups: BackupMeta[];
  searchQuery: string;
  onRestore: (backup: BackupMeta) => void;
  onRefresh: () => void;
}

export default function BackupTable({
  backups,
  searchQuery,
  onRestore,
  onRefresh,
}: Props) {
    const { message } = useAppMessage();

  // Filter is applied to the full in-memory list so search covers all pages, not just the current one.
  const filteredBackups = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return backups;
    return backups.filter(
      (s) => s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q),
    );
  }, [backups, searchQuery]);

  const [page, setPage] = useState(1);

  // Keep mobile cards sorted by created time (desc) to match the desktop table default.
  const sortedFilteredBackups = useMemo(() => {
    return [...filteredBackups].sort(
      (a, b) => dayjs(b.created_at).unix() - dayjs(a.created_at).unix(),
    );
  }, [filteredBackups]);

  useEffect(() => {
    setPage(1);
  }, [searchQuery]);

  const totalBackups = sortedFilteredBackups.length;
  const maxPage = Math.max(1, Math.ceil(totalBackups / PAGE_SIZE));
  const currentPage = Math.min(page, maxPage);
  const startIndex = (currentPage - 1) * PAGE_SIZE;
  const paginatedBackups = sortedFilteredBackups.slice(
    startIndex,
    startIndex + PAGE_SIZE,
  );

  /** Deletes a single backup by ID and refreshes the list on success. */
  const handleDelete = async (id: string) => {
    try {
      await api.deleteBackups([id]);
      message.success("备份删除成功");
      onRefresh();
    } catch {
      message.error("备份删除失败");
    }
  };

  /**
   * Shows a danger-confirmation modal warning the user about sensitive data
   * before triggering the zip download via the API.
   */
  const handleExport = (backup: BackupMeta) => {
    Modal.confirm({
      title: "敏感信息警告",
      content: "此备份可能包含敏感凭证信息。智能体工作区包含渠道凭证（如 bot token、app secret 等），模型供应商密钥包含 API Key。请勿将备份文件分享给他人。",
      okText: "确认导出",
      cancelText: "取消",
      okButtonProps: { danger: true },
      centered: true,
      onOk: async () => {
        try {
          await api.exportBackup(backup.id, backup.name);
        } catch {
          message.error("导出备份失败");
        }
      },
    });
  };

  const columns: ColumnsType<BackupMeta> = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 300,
      render: (id: string) => <span className={styles.idCell}>{id}</span>,
    },
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      ellipsis: true,
    },
    {
      title: "备份范围",
      key: "scope",
      width: 320,
      render: (_, record) => (
        <ScopeTags scope={record.scope} agentCount={record.agent_count} />
      ),
    },
    {
      title: "描述",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 160,
      render: (val: string) => (
        <Tooltip title={dayjs(val).format("YYYY-MM-DD HH:mm:ss")}>
          {dayjs(val).fromNow()}
        </Tooltip>
      ),
      sorter: (a, b) => dayjs(a.created_at).unix() - dayjs(b.created_at).unix(),
      defaultSortOrder: "descend",
    },
    {
      title: "操作",
      key: "actions",
      width: 200,
      render: (_, record) => (
        <span className={styles.actions}>
          <Button type="link" size="small" onClick={() => onRestore(record)}>
            {"恢复"}
          </Button>
          <Button type="link" size="small" onClick={() => handleExport(record)}>
            {"导出"}
          </Button>
          <Popconfirm
            title={"确定要删除此备份吗？此操作不可恢复。"}
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" size="small" danger>
              {"删除"}
            </Button>
          </Popconfirm>
        </span>
      ),
    },
  ];

  const renderMobileCard = (backup: BackupMeta) => (
    <Card
      key={backup.id}
      className={styles.mobileCard}
      size="small"
      title={
        <div className={styles.mobileCardHeader}>
          <Typography.Text
            ellipsis={{ tooltip: true }}
            className={styles.mobileId}
          >
            {backup.id}
          </Typography.Text>
          <span className={styles.mobileTime}>
            {dayjs(backup.created_at).format("YYYY-MM-DD HH:mm")}
          </span>
        </div>
      }
    >
      <div className={styles.mobileRow}>
        <span className={styles.mobileLabel}>{"名称"}</span>
        <Typography.Text
          ellipsis={{ tooltip: true }}
          className={styles.mobileValue}
        >
          {backup.name}
        </Typography.Text>
      </div>
      {backup.description ? (
        <div className={styles.mobileRow}>
          <span className={styles.mobileLabel}>
            {"描述"}
          </span>
          <Typography.Text
            ellipsis={{ tooltip: true }}
            className={styles.mobileValue}
          >
            {backup.description}
          </Typography.Text>
        </div>
      ) : null}
      <div className={styles.mobileRow}>
        <span className={styles.mobileLabel}>{"备份范围"}</span>
        <ScopeTags
          scope={backup.scope}
          agentCount={backup.agent_count}
          compact
        />
      </div>
      <div className={styles.mobileActions}>
        <Button
          type="primary"
          size="small"
          ghost
          onClick={() => onRestore(backup)}
        >
          {"恢复"}
        </Button>
        <Button size="small" onClick={() => handleExport(backup)}>
          {"导出"}
        </Button>
        <Popconfirm
          title={"确定要删除此备份吗？此操作不可恢复。"}
          onConfirm={() => handleDelete(backup.id)}
        >
          <Button size="small" danger>
            {"删除"}
          </Button>
        </Popconfirm>
      </div>
    </Card>
  );

  return (
    <>
      <Card className={styles.tableCard}>
        {backups.length === 0 ? (
          <Empty
            description={"暂无备份。创建一个备份来保存当前配置。"}
            style={{ padding: "40px 0" }}
          />
        ) : (
          <Table<BackupMeta>
            rowKey="id"
            dataSource={filteredBackups}
            columns={columns}
            size="middle"
            pagination={{
              pageSize: PAGE_SIZE,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 条`,
              pageSizeOptions: ["10", "20", "50"],
            }}
          />
        )}
      </Card>
      <div className={styles.mobileCards}>
        {totalBackups === 0 ? (
          <Empty
            description={"暂无备份。创建一个备份来保存当前配置。"}
            style={{ padding: "40px 0" }}
          />
        ) : (
          <>
            {paginatedBackups.map(renderMobileCard)}
            <div className={styles.mobilePagination}>
              <Pagination
                current={currentPage}
                pageSize={PAGE_SIZE}
                total={totalBackups}
                size="small"
                simple
                onChange={(p) => setPage(p)}
              />
            </div>
          </>
        )}
      </div>
    </>
  );
}
