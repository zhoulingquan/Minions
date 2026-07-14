import { Button, Tooltip, Dropdown } from "@agentscope-ai/design";
import type { ColumnsType } from "antd/es/table";
import type { MenuProps } from "antd";
import type { CronJobSchedule, CronJobSpecOutput } from "../../../../api/types";
import { CopyOutlined, MoreOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import { parseCron } from "./parseCron";
import styles from "../index.module.less";

type CronJob = CronJobSpecOutput;

interface ColumnHandlers {
  onToggleEnabled: (job: CronJob) => void;
  onExecuteNow: (job: CronJob) => void;
  onViewHistory: (job: CronJob) => void;
  onEdit: (job: CronJob) => void;
  onDelete: (jobId: string) => void;
}

const createCopyToClipboard = () => async (text: string) => {
  const { message } = useAppMessage();
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      message.success("已复制到剪贴板");
    } else {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      textArea.style.top = "-999999px";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      document.execCommand("copy");
      textArea.remove();
      message.success("已复制到剪贴板");
    }
  } catch (err) {
    console.error("Failed to copy text: ", err);
    message.error("复制到剪贴板失败");
  }
};

export const createColumns = (
  handlers: ColumnHandlers,
): ColumnsType<CronJob> => {
  const copyToClipboard = createCopyToClipboard();

  return [
    {
      title: "任务ID",
      dataIndex: "id",
      key: "id",
      width: 250,
      fixed: "left",
    },
    {
      title: "任务名称",
      dataIndex: "name",
      key: "name",
      width: 250,
    },
    {
      title: "启用状态",
      dataIndex: "enabled",
      key: "enabled",
      width: 100,
      render: (enabled: boolean) => (
        <span className={styles.statusIndicator}>
          <span
            className={`${styles.statusDot} ${
              enabled ? styles.enabled : styles.disabled
            }`}
          />
          {enabled ? "已启用" : "已禁用"}
        </span>
      ),
    },
    {
      title: "调度类型",
      dataIndex: ["schedule", "type"],
      key: "schedule_type",
      width: 140,
      render: (type: string) =>
        type === "once" ? "日程任务" : "循环任务",
    },
    {
      title: "执行时间（Cron）",
      dataIndex: "schedule",
      key: "cron",
      width: 180,
      render: (schedule: CronJobSchedule) => {
        if (schedule?.type === "once") {
          const displayText = schedule?.run_at
            ? dayjs(schedule.run_at).format("YYYY-MM-DD HH:mm")
            : "-";
          return (
            <Tooltip title={schedule?.run_at || displayText}>
              <span className={styles.cronText}>{displayText}</span>
            </Tooltip>
          );
        }
        const cron = schedule?.cron || "0 9 * * *";
        // Parse cron to friendly text
        const cronParts = parseCron(cron);
        let displayText = "";

        switch (cronParts.type) {
          case "hourly":
            displayText = "每小时";
            break;
          case "daily":
            displayText = `每天 ${String(
              cronParts.hour,
            ).padStart(2, "0")}:${String(cronParts.minute).padStart(2, "0")}`;
            break;
          case "weekly": {
            const dayNames = (cronParts.daysOfWeek || [])
              .map((d) => {
                const dayMap: Record<string, string> = {
                  mon: "周一",
                  tue: "周二",
                  wed: "周三",
                  thu: "周四",
                  fri: "周五",
                  sat: "周六",
                  sun: "周日",
                };
                return dayMap[d] || d;
              })
              .join(",");
            displayText = `每周 ${dayNames} ${String(cronParts.hour).padStart(2, "0")}:${String(
              cronParts.minute,
            ).padStart(2, "0")}`;
            break;
          }
          case "custom":
            displayText = cron;
            break;
        }

        return (
          <Tooltip
            title={
              <div>
                <div>Cron 表达式：{cron}</div>
                <div
                  className={styles.tableText}
                  style={{ opacity: 0.8, marginTop: 4 }}
                >
                  格式：分钟 小时 日 月 星期
                </div>
              </div>
            }
          >
            <span className={styles.cronText}>{displayText}</span>
          </Tooltip>
        );
      },
    },
    {
      title: "时区",
      dataIndex: ["schedule", "timezone"],
      key: "timezone",
      width: 170,
    },
    {
      title: "TaskType",
      dataIndex: "task_type",
      key: "task_type",
      width: 140,
    },
    {
      title: "消息内容",
      dataIndex: "text",
      key: "text",
      width: 200,
      ellipsis: {
        showTitle: true,
      },
      render: (text: string) => {
        if (!text) return "-";
        return (
          <Tooltip title={text}>
            <span className={styles.tableText}>{text}</span>
          </Tooltip>
        );
      },
    },
    {
      title: "请求内容",
      dataIndex: ["request", "input"],
      key: "request_input",
      width: 350,
      ellipsis: true,
      render: (input: unknown) => {
        if (!input) return "-";

        let displayText: string;
        let fullText: string;

        try {
          fullText = JSON.stringify(input, null, 2);
          displayText = JSON.stringify(input);
        } catch {
          fullText = String(input);
          displayText = fullText;
        }

        if (displayText.length <= 50) {
          return <code className={styles.codeText}>{displayText}</code>;
        }

        const truncatedText =
          displayText.length > 50
            ? displayText.substring(0, 50) + "..."
            : displayText;

        return (
          <Tooltip
            title={
              <div className={styles.tooltipContent}>
                <div className={styles.tooltipJsonContent}>{fullText}</div>
                <Button
                  type="text"
                  icon={<CopyOutlined />}
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    copyToClipboard(fullText);
                  }}
                  className={styles.copyButton}
                />
              </div>
            }
            placement="topLeft"
            overlayInnerStyle={{ maxWidth: 400 }}
          >
            <code className={styles.codeLink}>{truncatedText}</code>
          </Tooltip>
        );
      },
    },
    {
      title: "DispatchType",
      dataIndex: ["dispatch", "type"],
      key: "dispatch_type",
      width: 140,
    },
    {
      title: "DispatchChannel",
      dataIndex: ["dispatch", "channel"],
      key: "channel",
      width: 150,
    },
    {
      title: "DispatchTargetUserID",
      dataIndex: ["dispatch", "target", "user_id"],
      key: "target_user_id",
      width: 190,
    },
    {
      title: "DispatchTargetSessionID",
      dataIndex: ["dispatch", "target", "session_id"],
      key: "target_session_id",
      width: 210,
    },
    {
      title: "DispatchMode",
      dataIndex: ["dispatch", "mode"],
      key: "mode",
      width: 140,
    },
    {
      title: "RuntimeMaxConcurrency",
      dataIndex: ["runtime", "max_concurrency"],
      key: "max_concurrency",
      width: 210,
    },
    {
      title: "RuntimeTimeoutSeconds",
      dataIndex: ["runtime", "timeout_seconds"],
      key: "timeout_seconds",
      width: 210,
    },
    {
      title: "RuntimeMisfireGraceSeconds",
      dataIndex: ["runtime", "misfire_grace_seconds"],
      key: "misfire_grace_seconds",
      width: 240,
    },
    {
      title: "操作",
      key: "action",
      width: 320,
      fixed: "right",
      render: (_: unknown, record: CronJob) => {
        const menuItems: MenuProps["items"] = [
          {
            key: "edit",
            label: "编辑",
            onClick: () => handlers.onEdit(record),
          },
          {
            key: "delete",
            label: "删除",
            danger: true,
            onClick: () => handlers.onDelete(record.id),
          },
        ];

        return (
          <div className={styles.actionColumn}>
            <Button
              type="link"
              size="small"
              onClick={() => handlers.onToggleEnabled(record)}
            >
              {record.enabled ? "禁用" : "启用"}
            </Button>
            <Button
              type="link"
              size="small"
              onClick={() => handlers.onExecuteNow(record)}
            >
              立即执行
            </Button>
            <Button
              type="link"
              size="small"
              onClick={() => handlers.onViewHistory(record)}
            >
              执行记录
            </Button>
            <Dropdown menu={{ items: menuItems }} placement="bottomRight">
              <Button type="text" size="small" icon={<MoreOutlined />} />
            </Dropdown>
          </div>
        );
      },
    },
  ];
};
