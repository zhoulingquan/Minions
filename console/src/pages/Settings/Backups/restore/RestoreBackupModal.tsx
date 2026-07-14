/**
 * Final step in the restore flow: lets the user pick full or custom restore mode,
 * choose which agents / config items to include, and confirm before applying.
 *
 * On open it fetches the backup detail (real agent list from workspace_stats).
 * If the detail fetch fails the modal shows an error and disables the OK button,
 * since we need workspace_stats to build the explicit agent_ids list.
 * A "confirmed" checkbox gates the submit button to prevent accidental data loss.
 */
import { useState, useEffect, useMemo } from "react";
import {
  Modal,
  Checkbox,
  Radio,
  Alert,
  Input,
  Tag,
  Divider,
  Typography,
  Tooltip,
  Space,
} from "antd";
import { QuestionCircleOutlined } from "@ant-design/icons";
import api from "@/api";
import { useAppMessage } from "@/hooks/useAppMessage";
import type {
  BackupMeta,
  BackupDetail,
  RestoreBackupRequest,
} from "@/api/types/backup";
import type { AgentSummary } from "@/api/types/agents";
import { parseErrorDetail } from "@/utils/error";
import { isFullBackup } from "../shared/scope";
import BackupTrustDialog from "../trust/BackupTrustDialog";
import {
  trustModeFromErrorCode,
  type BackupTrustMode,
} from "../trust/trustErrors";
import RestoreAgentTable from "./RestoreAgentTable";
import styles from "./RestoreBackupModal.module.less";

const { Text } = Typography;

interface Props {
  open: boolean;
  backup: BackupMeta;
  agents: AgentSummary[];
  onClose: () => void;
  onSuccess: () => void;
}

type RestoreMode = "full" | "custom";
type RestoreStrategy = "preserve" | "restore";
type TrustPrompt = {
  mode: BackupTrustMode;
  request: RestoreBackupRequest;
};

export default function RestoreBackupModal({
  open,
  backup,
  agents,
  onClose,
  onSuccess,
}: Props) {
    const { message } = useAppMessage();
  const [loading, setLoading] = useState(false);

  const fullBackup = isFullBackup(backup.scope);
  const [restoreMode, setRestoreMode] = useState<RestoreMode>(
    fullBackup ? "full" : "custom",
  );
  // Foreign/legacy backups default to preserving local security and MCP
  // controls; local backups can restore them unless the user changes this.
  const [restoreStrategy, setRestoreStrategy] =
    useState<RestoreStrategy>("preserve");

  const [backupDetail, setBackupDetail] = useState<BackupDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailFailed, setDetailFailed] = useState(false);

  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [globalConfig, setGlobalConfig] = useState(
    backup.scope.include_global_config,
  );
  const [includeGlobalSkills, setIncludeGlobalSkills] = useState(
    backup.scope.include_global_skills,
  );
  const [includeSecrets, setIncludeSecrets] = useState(
    backup.scope.include_secrets,
  );
  const [defaultWorkspaceDir, setDefaultWorkspaceDir] = useState("");
  const [includeAgents, setIncludeAgents] = useState(
    backup.scope.include_agents,
  );
  const [confirmed, setConfirmed] = useState(false);
  const [trustPrompt, setTrustPrompt] = useState<TrustPrompt | null>(null);
  const [trustLoading, setTrustLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDetailLoading(true);
    setDetailFailed(false);
    setBackupDetail(null);
    api
      .getBackup(backup.id)
      .then((detail) => {
        setBackupDetail(detail);
        setSelectedAgents(Object.keys(detail.workspace_stats));
      })
      .catch(() => {
        setDetailFailed(true);
        message.error("备份详情加载失败，无法进行恢复操作");
      })
      .finally(() => setDetailLoading(false));
    // keying on backup.id is intentional: re-fetch when a different backup is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, backup.id]);

  useEffect(() => {
    if (!open) return;
    setRestoreMode(fullBackup ? "full" : "custom");
    setRestoreStrategy(
      backup.accepted_via_trust === false ? "restore" : "preserve",
    );
    setConfirmed(false);
    setTrustPrompt(null);
  }, [open, backup.id, backup.accepted_via_trust, fullBackup]);

  const existingAgentMap = useMemo(
    () => new Map(agents.map((a) => [a.id, a])),
    [agents],
  );

  // All agent IDs present in the backup (only available after detail loads).
  const allBackupAgentIds = useMemo(
    () => (backupDetail ? Object.keys(backupDetail.workspace_stats) : []),
    [backupDetail],
  );

  const allAgentRows = useMemo(() => {
    return allBackupAgentIds.map((aid) => {
      const agentInfo = existingAgentMap.get(aid);
      // For new (not-yet-existing) agents we can't look up the name from
      // /api/agents, so fall back to the name embedded inside the backup's
      // workspace/agent.json (exposed via workspace_stats[aid].name).
      const backupName = backupDetail?.workspace_stats?.[aid]?.name;
      return {
        key: aid,
        aid,
        name: agentInfo?.name ?? backupName ?? aid,
        isExisting: !!agentInfo,
        currentWorkspaceDir: agentInfo?.workspace_dir ?? "",
      };
    });
  }, [allBackupAgentIds, existingAgentMap, backupDetail]);

  const newCount = useMemo(
    () => allAgentRows.filter((r) => !r.isExisting).length,
    [allAgentRows],
  );
  const hasNewAgents = newCount > 0;

  const selectedExistingCount = useMemo(
    () => selectedAgents.filter((id) => existingAgentMap.has(id)).length,
    [selectedAgents, existingAgentMap],
  );
  const selectedNewCount = useMemo(
    () => selectedAgents.filter((id) => !existingAgentMap.has(id)).length,
    [selectedAgents, existingAgentMap],
  );

  const buildRestoreRequest = (): RestoreBackupRequest => {
    const isFull = restoreMode === "full";
    const doIncludeAgents = isFull ? true : includeAgents;
    const agent_ids = isFull
      ? allBackupAgentIds
      : includeAgents
      ? selectedAgents
      : [];

    return {
      mode: restoreMode,
      include_agents: doIncludeAgents,
      agent_ids,
      include_global_config: isFull ? true : globalConfig,
      include_secrets: isFull ? true : includeSecrets,
      include_global_skills: isFull ? true : includeGlobalSkills,
      default_workspace_dir: defaultWorkspaceDir.trim() || null,
      // Backend overlays local security/MCP config after the selected restore
      // mode has built its config payload.
      preserve_local_protected_config: restoreStrategy === "preserve",
    };
  };

  const finishRestore = async (request: RestoreBackupRequest) => {
    const response = await api.restoreBackup(backup.id, request);
    const preserved = response.preserved_local_keys ?? [];
    if (preserved.length > 0) {
      message.success(
        `备份恢复成功。已保留本地设置：${preserved.join(", ")}。请重启服务。`,
      );
    } else {
      message.success("备份恢复成功，请您重启服务。");
    }
    onSuccess();
    onClose();
  };

  const showRestoreFailure = (detail: Record<string, unknown> | null) => {
    if (detail?.code === "restore_target_busy") {
      const lockedPaths = Array.isArray(detail.locked_paths)
        ? detail.locked_paths.filter(
            (path): path is string => typeof path === "string" && !!path,
          )
        : [];

      message.error({
        content: (
          <div className={styles.restoreErrorMessage}>
            <div>{"备份恢复失败：以下目录仍被占用。请关闭正在使用这些目录的浏览器或进程后重试；如果仍然被锁定，请重启系统后再试。"}</div>
            {lockedPaths.length > 0 && (
              <div className={styles.lockedPathList}>
                {lockedPaths.map((path) => (
                  <div key={path} className={styles.lockedPath}>
                    {path}
                  </div>
                ))}
              </div>
            )}
          </div>
        ),
        duration: 8,
      });
      return;
    }

    message.error("备份恢复失败");
  };

  const handleOk = async () => {
    const request = buildRestoreRequest();
    setLoading(true);
    try {
      await finishRestore(request);
    } catch (err: unknown) {
      const detail = parseErrorDetail(err);
      const trustMode = trustModeFromErrorCode(detail?.code);
      if (trustMode) {
        setTrustPrompt({ mode: trustMode, request });
      } else {
        showRestoreFailure(detail);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleTrustConfirm = async () => {
    if (!trustPrompt) return;
    setTrustLoading(true);
    try {
      await finishRestore({
        ...trustPrompt.request,
        trust_mode: trustPrompt.mode,
      });
      setTrustPrompt(null);
    } catch (err: unknown) {
      showRestoreFailure(parseErrorDetail(err));
    } finally {
      setTrustLoading(false);
    }
  };

  const trustState =
    backupDetail?.accepted_via_trust ?? backup.accepted_via_trust ?? null;

  const summaryText =
    restoreMode === "custom" &&
    (selectedExistingCount > 0 || selectedNewCount > 0)
      ? `已选 ${selectedExistingCount} 个已存在 · ${selectedNewCount} 个新增`
      : null;

  // OK is disabled when detail hasn't loaded (we need workspace_stats to build agent_ids),
  // or when the user hasn't confirmed the destructive action.
  const okDisabled =
    !confirmed || detailFailed || (detailLoading && !backupDetail);

  return (
    <>
      <Modal
        title={"恢复备份"}
        open={open}
        onCancel={onClose}
        onOk={handleOk}
        confirmLoading={loading}
        okButtonProps={{ disabled: okDisabled, danger: true }}
        okText={"确认"}
        destroyOnHidden
        centered
        width={680}
      >
        <div className={styles.modalBody}>
          <div className={styles.backupInfoSection}>
            <Text strong style={{ fontSize: 14 }}>
              {backup.name}
            </Text>
            {backup.description && (
              <div className={styles.backupDescription}>
                {backup.description}
              </div>
            )}
          </div>

          <Alert
            showIcon
            type={
              trustState === false
                ? "success"
                : trustState === true
                ? "warning"
                : "info"
            }
            message={
              trustState === false
                ? "本地备份 - 默认完整恢复"
                : trustState === true
                ? "导入的备份 - 默认保留本地安全和 MCP 配置"
                : "历史备份 - 恢复前需要确认信任"
            }
            className={styles.trustBanner}
          />

          {detailFailed && (
            <Alert
              type="error"
              showIcon
              message={"备份详情加载失败，无法进行恢复操作"}
              className={styles.fullRestoreAlert}
            />
          )}

          {hasNewAgents && !detailFailed && (
            <div className={styles.workspaceDirSection}>
              <div className={styles.workspaceDirLabel}>
                {"智能体默认工作目录"}
                <Tooltip title={"待恢复的智能体的工作路径不存在时，智能体将保存在 <默认路径>/<智能体ID> 下，存在时则使用智能体的原始工作路径。"}>
                  <QuestionCircleOutlined className={styles.hintIcon} />
                </Tooltip>
              </div>
              <Input
                value={defaultWorkspaceDir}
                onChange={(e) => setDefaultWorkspaceDir(e.target.value)}
                placeholder={"留空时将使用 ~/.minions/workspaces"}
              />
            </div>
          )}

          <Divider className={styles.dividerTop} />

          <div className={styles.restoreModeSection}>
            <div className={styles.restoreModeLabel}>
              {"恢复模式"}
            </div>
            <Radio.Group
              value={restoreMode}
              onChange={(e) => setRestoreMode(e.target.value)}
              className={styles.radioGroup}
            >
              <Radio value="full" disabled={!fullBackup}>
                <div className={styles.radioOption}>
                  <div className={styles.radioOptionHeader}>
                    <Text strong>{"整体恢复"}</Text>
                    {!fullBackup && (
                      <Tag color="default" className={styles.radioDisabledTag}>
                        {"仅完整备份可用"}
                      </Tag>
                    )}
                  </div>
                  <Text type="secondary" className={styles.radioDesc}>
                    {"完全替换当前实例的所有内容，包括所有智能体、全局配置、全局技能和密钥"}
                  </Text>
                </div>
              </Radio>
              <Radio value="custom">
                <div className={styles.radioOption}>
                  <Text strong>{"自定义恢复"}</Text>
                  <Text type="secondary" className={styles.radioDesc}>
                    {"选择要恢复的内容，如部分智能体、配置等；当前已有但不在本次恢复范围内的其他智能体不会被移除"}
                  </Text>
                </div>
              </Radio>
            </Radio.Group>
          </div>

          <div className={styles.strategySection}>
            <div className={styles.strategyLabel}>
              {"恢复策略"}
            </div>
            <Radio.Group
              value={restoreStrategy}
              onChange={(e) => setRestoreStrategy(e.target.value)}
              className={styles.radioGroup}
            >
              <Radio value="preserve">
                <div className={styles.radioOption}>
                  <Text strong>
                    {"保留本地安全和 MCP 配置"}
                  </Text>
                  <Text type="secondary" className={styles.radioDesc}>
                    {"保留当前实例的安全防护和 MCP 配置。"}
                  </Text>
                </div>
              </Radio>
              <Radio value="restore">
                <div className={styles.radioOption}>
                  <Text strong>
                    {"从备份恢复这些设置"}
                  </Text>
                  <Text type="secondary" className={styles.radioDesc}>
                    {"使用备份中的安全和 MCP 配置。"}
                  </Text>
                </div>
              </Radio>
            </Radio.Group>
          </div>

          {restoreMode === "full" && (
            <Alert
              type="warning"
              showIcon
              message={"整体恢复将完全替换当前实例的所有内容（包括所有智能体、全局配置、全局技能和密钥），操作不可撤销。恢复期间相关功能不可用，恢复完成后请重启服务。"}
              className={styles.fullRestoreAlert}
            />
          )}

          {restoreMode === "custom" && (
            <Space
              direction="vertical"
              size={0}
              className={styles.customOptions}
            >
              {backup.scope.include_agents && (
                <RestoreAgentTable
                  allAgentRows={allAgentRows}
                  selectedAgents={selectedAgents}
                  onSelectionChange={setSelectedAgents}
                  detailLoading={detailLoading}
                  defaultWorkspaceDir={defaultWorkspaceDir}
                  includeAgents={includeAgents}
                  onIncludeAgentsChange={setIncludeAgents}
                  summaryText={summaryText}
                />
              )}

              {backup.scope.include_global_config && (
                <div className={styles.checkboxRow}>
                  <Checkbox
                    checked={globalConfig}
                    onChange={(e) => setGlobalConfig(e.target.checked)}
                  >
                    {"全局设置"}
                  </Checkbox>
                </div>
              )}

              {backup.scope.include_global_skills && (
                <div className={styles.checkboxRow}>
                  <Checkbox
                    checked={includeGlobalSkills}
                    onChange={(e) => setIncludeGlobalSkills(e.target.checked)}
                  >
                    {"全局技能"}
                  </Checkbox>
                </div>
              )}

              {backup.scope.include_secrets && (
                <div className={styles.checkboxRow}>
                  <Checkbox
                    checked={includeSecrets}
                    onChange={(e) => setIncludeSecrets(e.target.checked)}
                  >
                    {"密钥信息"}
                  </Checkbox>
                  <div className={styles.secretsHint}>
                    {"包含模型供应商密钥（API Key）和环境变量等敏感信息"}
                  </div>
                </div>
              )}
            </Space>
          )}

          <Divider className={styles.dividerBottom} />

          {restoreMode === "custom" && (
            <Alert
              type="warning"
              showIcon
              message={
                <ul className={styles.restoreWarningList}>
                  <li>{"恢复操作会修改当前配置，此操作不可撤销。"}</li>
                  <li>{"恢复期间相关功能不可用，恢复完成后请重启服务。"}</li>
                </ul>
              }
              className={styles.customRestoreAlert}
            />
          )}

          <Checkbox
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          >
            {"我确认要恢复此备份"}
          </Checkbox>
        </div>
      </Modal>
      <BackupTrustDialog
        open={!!trustPrompt}
        mode={trustPrompt?.mode ?? "legacy"}
        backupName={backup.name}
        confirmLoading={trustLoading}
        onConfirm={handleTrustConfirm}
        onCancel={() => setTrustPrompt(null)}
      />
    </>
  );
}
