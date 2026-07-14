/**
 * Expandable agent selection table used inside RestoreBackupModal.
 * Shows each agent from the backup with its restore action (replace/add),
 * its destination workspace path, and a search box that filters without
 * losing selections outside the current filtered view.
 */
import { useState, useMemo } from "react";
import type { Key } from "react";
import { Checkbox, Input, Tag, Table, Spin, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { SearchOutlined, RightOutlined } from "@ant-design/icons";
import styles from "./RestoreAgentTable.module.less";

const { Text } = Typography;

export interface AgentRow {
  key: string;
  aid: string;
  name: string;
  isExisting: boolean;
  currentWorkspaceDir: string;
}

interface Props {
  allAgentRows: AgentRow[];
  selectedAgents: string[];
  onSelectionChange: (ids: string[]) => void;
  detailLoading: boolean;
  defaultWorkspaceDir: string;
  includeAgents: boolean;
  onIncludeAgentsChange: (checked: boolean) => void;
  summaryText: string | null;
}

export default function RestoreAgentTable({
  allAgentRows,
  selectedAgents,
  onSelectionChange,
  detailLoading,
  defaultWorkspaceDir,
  includeAgents,
  onIncludeAgentsChange,
  summaryText,
}: Props) {
    const [agentSearch, setAgentSearch] = useState("");
  const [agentsExpanded, setAgentsExpanded] = useState(true);

  const filteredAgentRows = useMemo(() => {
    const q = agentSearch.trim().toLowerCase();
    if (!q) return allAgentRows;
    return allAgentRows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) || r.aid.toLowerCase().includes(q),
    );
  }, [allAgentRows, agentSearch]);

  const allAgentIds = useMemo(
    () => allAgentRows.map((r) => r.aid),
    [allAgentRows],
  );

  const allSelected =
    allAgentIds.length > 0 &&
    allAgentIds.every((id) => selectedAgents.includes(id));
  const someSelected = selectedAgents.length > 0 && !allSelected;

  /** Selects or clears all agent IDs in the unfiltered list. */
  const handleSelectAll = (checked: boolean) => {
    onSelectionChange(checked ? [...allAgentIds] : []);
  };

  // When selection changes inside the (possibly filtered) table, preserve
  // selections that are outside the current filtered view.
  const handleTableSelectionChange = (keys: Key[]) => {
    const filteredIds = new Set(filteredAgentRows.map((r) => r.aid));
    const kept = selectedAgents.filter((id) => !filteredIds.has(id));
    onSelectionChange([...kept, ...(keys as string[])]);
  };

  /**
   * Computes the destination workspace path for a new (not-yet-existing) agent.
   * If the user provided a default directory, appends the agent ID under it;
   * otherwise falls back to the i18n placeholder shown in the table cell.
   */
  const getNewAgentDestPath = (aid: string): string => {
    const base = defaultWorkspaceDir.trim();
    if (base) return `${base.replace(/[/\\]+$/, "")}/${aid}`;
    return `<默认路径>/${aid}`;
  };

  const agentColumns: TableColumnsType<AgentRow> = [
    {
      title: "智能体",
      key: "name",
      render: (_, row) => (
        <div>
          <Text strong className={styles.agentName}>
            {row.name}
          </Text>
          {row.name !== row.aid && (
            <Text type="secondary" className={styles.agentId}>
              ({row.aid})
            </Text>
          )}
          <Tag
            color={row.isExisting ? "blue" : "green"}
            className={styles.agentActionTag}
          >
            {row.isExisting
              ? "替换已有"
              : "新增"}
          </Tag>
        </div>
      ),
    },
    {
      title: "工作目录",
      key: "workspace",
      ellipsis: true,
      render: (_, row) => (
        <Text
          type="secondary"
          className={styles.agentWorkspaceText}
          ellipsis={{
            tooltip: row.isExisting
              ? row.currentWorkspaceDir
              : getNewAgentDestPath(row.aid),
          }}
        >
          {row.isExisting
            ? row.currentWorkspaceDir || row.aid
            : getNewAgentDestPath(row.aid)}
        </Text>
      ),
    },
  ];

  return (
    <div>
      <div className={styles.agentsRowHeader}>
        <Checkbox
          checked={includeAgents}
          onChange={(e) => {
            onIncludeAgentsChange(e.target.checked);
            setAgentsExpanded(e.target.checked);
          }}
        >
          {"智能体工作区"}
          {includeAgents && detailLoading && (
            <Spin size="small" style={{ marginLeft: 8 }} />
          )}
          {includeAgents && !detailLoading && summaryText && (
            <Text type="secondary" className={styles.agentSummaryText}>
              — {summaryText}
            </Text>
          )}
        </Checkbox>
        {includeAgents && (
          <span
            onClick={() => setAgentsExpanded(!agentsExpanded)}
            className={styles.expandToggle}
          >
            <RightOutlined
              className={`${styles.expandIcon}${
                agentsExpanded ? ` ${styles.open}` : ""
              }`}
            />
          </span>
        )}
      </div>

      {includeAgents && agentsExpanded && (
        <div className={styles.agentsContent}>
          {detailLoading ? (
            <div className={styles.agentsLoading}>
              <Spin />
              <div className={styles.agentsLoadingText}>
                {"正在加载智能体列表..."}
              </div>
            </div>
          ) : (
            <>
              <div className={styles.agentSearchToolbar}>
                <Input
                  size="small"
                  prefix={
                    <SearchOutlined
                      style={{ color: "var(--ant-color-text-quaternary)" }}
                    />
                  }
                  placeholder={"按名称或 ID 搜索智能体..."}
                  value={agentSearch}
                  onChange={(e) => setAgentSearch(e.target.value)}
                  allowClear
                  className={styles.agentSearchInput}
                />
                <Text type="secondary" className={styles.selectAllCount}>
                  ({selectedAgents.length}/{allAgentIds.length})
                </Text>
              </div>

              <Table<AgentRow>
                rowKey="aid"
                dataSource={filteredAgentRows}
                columns={agentColumns}
                size="small"
                rowSelection={{
                  selectedRowKeys: selectedAgents,
                  onChange: handleTableSelectionChange,
                  columnTitle: (
                    <Checkbox
                      checked={allSelected}
                      indeterminate={someSelected}
                      onChange={(e) => handleSelectAll(e.target.checked)}
                    />
                  ),
                  renderCell: (_checked, _row, _index, originNode) =>
                    originNode,
                }}
                pagination={{
                  pageSize: 10,
                  showSizeChanger: false,
                  showTotal: (total) =>
                    agentSearch
                      ? `搜索到 ${total} 个，共 ${allAgentIds.length} 个`
                      : `共 ${total} 个智能体`,
                  size: "small",
                  hideOnSinglePage: true,
                }}
                locale={{ emptyText: "备份中没有智能体工作区" }}
                className={styles.agentTable}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}
