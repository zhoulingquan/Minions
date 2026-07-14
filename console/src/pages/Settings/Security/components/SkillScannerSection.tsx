import { useState, useCallback } from "react";
import {
  Card,
  InputNumber,
  Table,
  Tag,
  Button,
  Modal,
  Tooltip,
  Empty,
  Tabs,
} from "@agentscope-ai/design";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import { Select, Space } from "antd";
import { Trash2, ShieldCheck, Eye } from "lucide-react";
import { useSkillScanner } from "../useSkillScanner";
import type {
  BlockedSkillRecord,
  BlockedSkillFinding,
  SkillScannerWhitelistEntry,
  SkillScannerMode,
} from "../../../../api/modules/security";
import { skillApi } from "../../../../api/modules/skill";
import { useTheme } from "../../../../contexts/ThemeContext";
import styles from "../index.module.less";

function FindingsModal({
  findings,
  skillName,
  open,
  onClose,
}: {
  findings: BlockedSkillFinding[];
  skillName: string;
  open: boolean;
  onClose: () => void;
}) {

  return (
    <Modal
      title={`${"查看详情"} - ${skillName}`}
      open={open}
      onCancel={onClose}
      footer={null}
      width={700}
    >
      <Table
        dataSource={findings}
        rowKey={(_, idx) => String(idx)}
        pagination={false}
        size="small"
        columns={[
          {
            title: "Title",
            dataIndex: "title",
            key: "title",
            width: 200,
          },
          {
            title: "File",
            key: "location",
            width: 160,
            render: (_: unknown, record: BlockedSkillFinding) =>
              record.line_number
                ? `${record.file_path}:${record.line_number}`
                : record.file_path,
          },
          {
            title: "Description",
            dataIndex: "description",
            key: "description",
            ellipsis: true,
          },
        ]}
      />
    </Modal>
  );
}

export function SkillScannerSection() {
    const { isDark } = useTheme();
  const darkBtnStyle = isDark ? { color: "rgba(255,255,255,0.75)" } : undefined;
  const {
    config,
    blockedHistory,
    whitelist,
    loading,
    updateConfig,
    addToWhitelist,
    removeFromWhitelist,
    removeBlockedEntry,
    clearBlockedHistory,
  } = useSkillScanner();

  const { message } = useAppMessage();
  const [saving, setSaving] = useState(false);
  const [findingsModal, setFindingsModal] = useState<{
    open: boolean;
    findings: BlockedSkillFinding[];
    skillName: string;
  }>({ open: false, findings: [], skillName: "" });

  const handleModeChange = useCallback(
    async (mode: SkillScannerMode) => {
      setSaving(true);
      const ok = await updateConfig({ mode });
      if (ok) message.success("技能扫描器设置已保存");
      else message.error("保存技能扫描器设置失败");
      setSaving(false);
    },
    [message, updateConfig],
  );

  const [pendingTimeout, setPendingTimeout] = useState<number | null>(null);

  const handleTimeoutBlur = useCallback(async () => {
    const value = pendingTimeout;
    if (value === null || value < 5 || value > 300) {
      setPendingTimeout(null);
      return;
    }
    setSaving(true);
    const ok = await updateConfig({ timeout: value });
    if (ok) message.success("技能扫描器设置已保存");
    else message.error("保存技能扫描器设置失败");
    setPendingTimeout(null);
    setSaving(false);
  }, [message, pendingTimeout, updateConfig]);

  const handleAllowSkill = useCallback(
    async (record: BlockedSkillRecord, index: number) => {
      const ok = await addToWhitelist(record.skill_name, record.content_hash);
      if (ok) {
        message.success("技能已加入白名单");
        await removeBlockedEntry(index);
      } else {
        message.error("加入白名单失败");
      }
    },
    [addToWhitelist, message, removeBlockedEntry],
  );

  const handleRemoveWhitelist = useCallback(
    async (skillName: string) => {
      Modal.confirm({
        title: "确定将此技能从白名单中移除？",
        content: "移除后该技能将同时被禁用。",
        onOk: async () => {
          const ok = await removeFromWhitelist(skillName);
          if (!ok) {
            message.error("从白名单移除失败");
            return;
          }
          try {
            await skillApi.disableSkill(skillName);
            message.success(
              "技能已从白名单移除并已禁用",
            );
          } catch {
            message.success("技能已从白名单移除");
          }
        },
      });
    },
    [message, removeFromWhitelist],
  );

  const handleClearHistory = useCallback(() => {
    Modal.confirm({
      title: "确定清除所有扫描告警吗？",
      onOk: async () => {
        await clearBlockedHistory();
      },
    });
  }, [clearBlockedHistory]);

  if (loading || !config) return null;

  const enabled = config.mode !== "off";

  const blockedColumns = [
    {
      title: "技能",
      dataIndex: "skill_name",
      key: "skill_name",
      width: 180,
    },
    {
      title: "动作",
      dataIndex: "action",
      key: "action",
      width: 100,
      render: (action: string) => (
        <Tag color={action === "blocked" ? "red" : "orange"}>
          {action === "blocked"
            ? "已拦截"
            : "已提醒"}
        </Tag>
      ),
    },
    {
      title: "时间",
      dataIndex: "blocked_at",
      key: "blocked_at",
      width: 180,
      render: (val: string) => {
        try {
          return new Date(val).toLocaleString();
        } catch {
          return val;
        }
      },
    },
    {
      title: "操作",
      key: "actions",
      width: 200,
      render: (_: unknown, record: BlockedSkillRecord, index: number) => (
        <Space size="small">
          <Tooltip title={"查看详情"}>
            <Button
              type="text"
              size="middle"
              style={darkBtnStyle}
              onClick={() =>
                setFindingsModal({
                  open: true,
                  findings: record.findings,
                  skillName: record.skill_name,
                })
              }
            >
              <Eye size={14} />
            </Button>
          </Tooltip>
          <Tooltip title={"加入白名单"}>
            <Button
              type="text"
              size="middle"
              style={darkBtnStyle}
              onClick={() => handleAllowSkill(record, index)}
            >
              <ShieldCheck size={14} />
            </Button>
          </Tooltip>
          <Tooltip title={"删除"}>
            <Button
              type="text"
              size="middle"
              danger
              onClick={() => removeBlockedEntry(index)}
            >
              <Trash2 size={14} />
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ];

  const whitelistColumns = [
    {
      title: "技能",
      dataIndex: "skill_name",
      key: "skill_name",
      width: 200,
    },
    {
      title: "内容哈希",
      dataIndex: "content_hash",
      key: "content_hash",
      width: 200,
      ellipsis: true,
      render: (hash: string) =>
        hash ? (
          <Tooltip title={hash}>
            <code className={styles.codeHash}>{hash.substring(0, 16)}...</code>
          </Tooltip>
        ) : (
          <span style={{ color: "#999" }}>any</span>
        ),
    },
    {
      title: "添加时间",
      dataIndex: "added_at",
      key: "added_at",
      width: 180,
      render: (val: string) => {
        try {
          return new Date(val).toLocaleString();
        } catch {
          return val;
        }
      },
    },
    {
      title: "操作",
      key: "actions",
      width: 100,
      render: (_: unknown, record: SkillScannerWhitelistEntry) => (
        <Tooltip title={"移除"}>
          <Button
            type="text"
            size="middle"
            danger
            onClick={() => handleRemoveWhitelist(record.skill_name)}
          >
            <Trash2 size={14} />
          </Button>
        </Tooltip>
      ),
    },
  ];

  return (
    <>
      <Card className={styles.formCard}>
        <div className={styles.skillScannerConfig}>
          <div className={styles.skillScannerConfigItem}>
            <Tooltip title={"控制扫描器如何处理不安全的技能：拦截、仅提醒或关闭"}>
              <span className={styles.skillScannerLabel}>
                {"扫描模式"}
              </span>
            </Tooltip>
            <Select
              value={config.mode}
              onChange={handleModeChange}
              disabled={saving}
              style={{ width: 140 }}
              options={[
                {
                  value: "block",
                  label: "拦截",
                },
                { value: "warn", label: "仅提醒" },
                { value: "off", label: "关闭" },
              ]}
            />
          </div>

          <div className={styles.skillScannerConfigItem}>
            <Tooltip title={"等待扫描完成的最长时间（5-300秒）"}>
              <span className={styles.skillScannerLabel}>
                {"扫描超时（秒）"}
              </span>
            </Tooltip>
            <InputNumber
              min={5}
              max={300}
              value={pendingTimeout ?? config.timeout}
              onChange={(v) => setPendingTimeout(v)}
              onBlur={handleTimeoutBlur}
              onPressEnter={handleTimeoutBlur}
              disabled={!enabled}
              style={{ width: 100 }}
            />
          </div>
        </div>
      </Card>

      <Tabs
        className={styles.innerTabs}
        items={[
          {
            key: "scanAlerts",
            label: (
              <span>
                {"扫描告警"}
                {blockedHistory.length > 0 && (
                  <span className={styles.tabBadge}>
                    {blockedHistory.length}
                  </span>
                )}
              </span>
            ),
            children: (
              <div className={styles.tabPanelContent}>
                {blockedHistory.length > 0 && (
                  <div className={styles.tabPanelHeader}>
                    <Button size="small" danger onClick={handleClearHistory}>
                      {"清除全部"}
                    </Button>
                  </div>
                )}
                <Card className={styles.tableCard}>
                  {blockedHistory.length === 0 ? (
                    <div className={styles.emptyState}>
                      <Empty
                        description={
                          <span className={styles.emptyText}>
                            {"暂无安全告警"}
                          </span>
                        }
                      />
                    </div>
                  ) : (
                    <Table
                      dataSource={blockedHistory}
                      columns={blockedColumns}
                      rowKey={(_, idx) => String(idx)}
                      pagination={false}
                      size="small"
                    />
                  )}
                </Card>
              </div>
            ),
          },
          {
            key: "whitelist",
            label: (
              <span>
                {"白名单"}
                {whitelist.length > 0 && (
                  <span className={styles.tabBadge}>{whitelist.length}</span>
                )}
              </span>
            ),
            children: (
              <div className={styles.tabPanelContent}>
                <Card className={styles.tableCard}>
                  {whitelist.length === 0 ? (
                    <div className={styles.emptyState}>
                      <Empty
                        description={
                          <span className={styles.emptyText}>
                            {"暂无白名单技能"}
                          </span>
                        }
                      />
                    </div>
                  ) : (
                    <Table
                      dataSource={whitelist}
                      columns={whitelistColumns}
                      rowKey="skill_name"
                      pagination={false}
                      size="small"
                    />
                  )}
                </Card>
              </div>
            ),
          },
        ]}
      />

      <FindingsModal
        findings={findingsModal.findings}
        skillName={findingsModal.skillName}
        open={findingsModal.open}
        onClose={() =>
          setFindingsModal({ open: false, findings: [], skillName: "" })
        }
      />
    </>
  );
}
