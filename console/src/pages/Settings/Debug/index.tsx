import {
  Alert,
  Button,
  Card,
  Input,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { PageHeader } from "@/components/PageHeader";
import { useDebugLogs, backendLevelColor } from "./useDebugLogs";
import { LogViewer } from "./components";
import styles from "./index.module.less";

const { Text } = Typography;

export default function DebugPage() {
    const {
    backendLogs,
    initialLoading,
    backendError,
    autoRefresh,
    setAutoRefresh,
    backendNewestFirst,
    setBackendNewestFirst,
    backendLevel,
    setBackendLevel,
    backendQuery,
    setBackendQuery,
    filteredBackendLines,
    loadBackendLogs,
    handleCopyBackend,
  } = useDebugLogs();

  return (
    <div className={styles.debugPage}>
      <PageHeader
        parent={"设置"}
        current={"调试"}
      />

      <div className={styles.content}>
        <Alert
          type="info"
          showIcon
          className={styles.tipAlert}
          message={"查看后端守护进程日志文件，便于排查问题。在此页面打开时日志会自动刷新。"}
        />
        <Card
          title={"后端日志"}
          extra={
            <Space size="middle" className={styles.cardExtra}>
              <Text type="secondary">
                {"最新在前"}
              </Text>
              <Switch
                checked={backendNewestFirst}
                onChange={setBackendNewestFirst}
              />
              <Text type="secondary">
                {"自动刷新"}
              </Text>
              <Switch checked={autoRefresh} onChange={setAutoRefresh} />
            </Space>
          }
        >
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <div className={styles.toolbar}>
              <div className={styles.toolbarLeft}>
                <Select
                  className={styles.levelSelect}
                  value={backendLevel}
                  onChange={(v) => setBackendLevel(v)}
                  options={[
                    { value: "all", label: "全部" },
                    {
                      value: "error",
                      label: (
                        <Tag color={backendLevelColor("error")}>ERROR</Tag>
                      ),
                    },
                    {
                      value: "warning",
                      label: (
                        <Tag color={backendLevelColor("warning")}>WARNING</Tag>
                      ),
                    },
                    {
                      value: "info",
                      label: <Tag color={backendLevelColor("info")}>INFO</Tag>,
                    },
                    {
                      value: "debug",
                      label: (
                        <Tag color={backendLevelColor("debug")}>DEBUG</Tag>
                      ),
                    },
                  ]}
                />
                <Input
                  className={styles.searchInput}
                  value={backendQuery}
                  onChange={(e) => setBackendQuery(e.target.value)}
                  placeholder={"搜索后端日志..."}
                  allowClear
                />
                {backendLogs?.updated_at && (
                  <Text type="secondary" className={styles.updatedAt}>
                    {"更新时间"}:{" "}
                    {dayjs(backendLogs.updated_at * 1000).format(
                      "YYYY-MM-DD HH:mm:ss",
                    )}
                  </Text>
                )}
              </div>
              <div className={styles.toolbarRight}>
                <Button
                  onClick={() => void loadBackendLogs({ successToast: true })}
                >
                  {"刷新后端日志"}
                </Button>
                <Button onClick={() => void handleCopyBackend()}>
                  {"复制后端日志"}
                </Button>
              </div>
            </div>

            {backendLogs?.path && (
              <div className={styles.logPath}>
                <Text type="secondary" className={styles.logPathLabel}>
                  {"日志文件"}
                </Text>
                <code className={styles.logPathValue}>{backendLogs.path}</code>
              </div>
            )}

            {backendError ? (
              <Alert message={backendError} type="error" showIcon />
            ) : !backendLogs?.exists ? (
              <Alert
                message={"暂未找到后端日志文件。"}
                type="warning"
                showIcon
              />
            ) : null}

            <LogViewer
              lines={filteredBackendLines}
              query={backendQuery}
              loading={initialLoading}
            />
          </Space>
        </Card>
      </div>
    </div>
  );
}
