import { Table, Button, Space, Popconfirm, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { EditOutlined, DeleteOutlined, RobotOutlined } from "@ant-design/icons";
import { EyeOff, Eye } from "lucide-react";
import type { AgentSummary } from "../../../../api/types/agents";
import { useTheme } from "../../../../contexts/ThemeContext";
import { getAgentDisplayName } from "../../../../utils/agentDisplayName";
import { SortableAgentRow, DragHandle } from "./SortableAgentRow";
import { providerIcon } from "../../Models/components/providerIcon";
import styles from "../index.module.less";

interface AgentTableProps {
  agents: AgentSummary[];
  loading: boolean;
  reordering: boolean;
  onEdit: (agent: AgentSummary) => void;
  onDelete: (agentId: string) => void;
  onToggle: (agentId: string, currentEnabled: boolean) => void;
  onReorder: (activeId: string, overId: string) => void;
}

export function AgentTable({
  agents,
  loading,
  reordering,
  onEdit,
  onDelete,
  onToggle,
  onReorder,
}: AgentTableProps) {
    const { isDark } = useTheme();
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 6,
      },
    }),
  );

  const disabledStyle: React.CSSProperties = isDark
    ? { color: "rgba(255,255,255,0.35)", opacity: 1 }
    : {};

  const iconStyle: React.CSSProperties = isDark
    ? { color: "rgba(255,255,255,0.85)" }
    : {};

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) {
      return;
    }

    onReorder(String(active.id), String(over.id));
  };

  const columns: ColumnsType<AgentSummary> = [
    {
      title: "",
      key: "sort",
      width: 56,
      align: "center",
      render: () => (
        <Tooltip title={"拖拽调整智能体顺序"}>
          <span>
            <DragHandle disabled={reordering || loading} />
          </span>
        </Tooltip>
      ),
    },
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      width: 300,
      render: (_text: string, record: AgentSummary) => (
        <Space>
          <RobotOutlined
            style={{
              fontSize: 16,
              opacity: record.enabled ? 1 : 0.5,
            }}
          />
          <span style={{ opacity: record.enabled ? 1 : 0.5 }}>
            {getAgentDisplayName(record)}
          </span>
          {!record.enabled && <Tag color="error">{"已禁用"}</Tag>}
        </Space>
      ),
    },
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
    },
    {
      title: "描述",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: "工作区路径",
      dataIndex: "workspace_dir",
      key: "workspace_dir",
      ellipsis: true,
    },
    {
      title: "模型",
      key: "active_model",
      width: 260,
      ellipsis: true,
      render: (_value: unknown, record: AgentSummary) => {
        if (!record.active_model) {
          return (
            <span style={{ opacity: 0.45 }}>{"使用全局默认"}</span>
          );
        }
        return (
          <Space size={6}>
            <img
              src={providerIcon(record.active_model.provider_id)}
              alt=""
              style={{ width: 16, height: 16 }}
            />
            <Tooltip title={record.active_model.model}>
              <span>{record.active_model.model}</span>
            </Tooltip>
          </Space>
        );
      },
    },
    {
      title: "操作",
      key: "actions",
      render: (_value: unknown, record: AgentSummary) => (
        <Space>
          <Button
            type="text"
            size="middle"
            icon={<EditOutlined />}
            onClick={() => onEdit(record)}
            disabled={record.id === "default"}
            style={record.id === "default" ? disabledStyle : iconStyle}
            title={
              record.id === "default"
                ? "默认智能体不允许编辑"
                : undefined
            }
          />
          <Popconfirm
            title={
              record.enabled
                ? "确认禁用智能体"
                : "确认启用智能体"
            }
            description={
              record.enabled
                ? "禁用后该智能体不会启动运行实例，但仍可在列表中查看"
                : "启用后该智能体将可以正常切换使用"
            }
            onConfirm={() => onToggle(record.id, record.enabled)}
            disabled={record.id === "default"}
            okText={"确认"}
            cancelText={"取消"}
          >
            <Button
              type="text"
              size="middle"
              icon={record.enabled ? <EyeOff size={14} /> : <Eye size={14} />}
              disabled={record.id === "default"}
              style={record.id === "default" ? disabledStyle : iconStyle}
              title={
                record.id === "default"
                  ? "默认智能体不允许禁用"
                  : undefined
              }
            />
          </Popconfirm>
          <Popconfirm
            title={"确认删除智能体"}
            description={"删除后智能体将不可用，但工作区文件会保留"}
            onConfirm={() => onDelete(record.id)}
            disabled={record.id === "default"}
            okText={"确认"}
            cancelText={"取消"}
          >
            <Button
              type="link"
              size="middle"
              danger
              icon={<DeleteOutlined />}
              disabled={record.id === "default"}
              style={record.id === "default" ? disabledStyle : undefined}
              title={
                record.id === "default"
                  ? "默认智能体不允许删除"
                  : undefined
              }
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className={styles.tableCard}>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={agents.map((agent) => agent.id)}
          strategy={verticalListSortingStrategy}
        >
          <Table
            dataSource={agents}
            columns={columns}
            loading={loading}
            rowKey="id"
            components={{
              body: {
                row: SortableAgentRow,
              },
            }}
            pagination={false}
          />
        </SortableContext>
      </DndContext>
    </div>
  );
}
