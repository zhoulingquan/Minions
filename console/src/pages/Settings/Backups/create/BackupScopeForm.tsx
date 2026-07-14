/**
 * Controlled form section for choosing what to include in a backup.
 * Handles the full/partial radio toggle and the four partial-mode checkboxes
 * (agents, global config, skill pool, secrets). Extracted from CreateBackupModal
 * so it can be unit-tested and potentially reused independently.
 */
import { Checkbox, Radio } from "antd";
import type { AgentSummary } from "@/api/types/agents";
import AgentMultiSelect from "./AgentMultiSelect";
import styles from "./BackupScopeForm.module.less";

export interface ScopeFormValue {
  backupMode: "full" | "partial";
  selectedAgents: string[];
  globalConfig: boolean;
  includeGlobalSkills: boolean;
  includeSecrets: boolean;
}

interface Props {
  value: ScopeFormValue;
  onChange: (next: ScopeFormValue) => void;
  agents: AgentSummary[];
}

/**
 * Full/partial backup mode selector plus scope checkboxes.
 * Extracted from CreateBackupModal so it can be tested and reused independently.
 */
export default function BackupScopeForm({ value, onChange, agents }: Props) {

  /** Shallow-merges a partial update into the current form value. */
  const set = (partial: Partial<ScopeFormValue>) =>
    onChange({ ...value, ...partial });

  return (
    <div className={styles.form}>
      <div className={styles.section}>
        <div className={styles.sectionLabel}>{"备份模式"}</div>
        <Radio.Group
          value={value.backupMode}
          onChange={(e) => set({ backupMode: e.target.value })}
          className={styles.radioGroup}
        >
          <Radio value="full">
            <strong>{"完整备份"}</strong>
            <div className={styles.radioDesc}>{"备份所有内容，包括所有智能体工作区、全局设置、全局技能和密钥信息"}</div>
          </Radio>
          <Radio value="partial">
            <strong>{"部分备份"}</strong>
            <div className={styles.radioDesc}>
              {"自定义选择要备份的内容"}
            </div>
          </Radio>
        </Radio.Group>
      </div>

      {value.backupMode === "partial" && (
        <div className={styles.partialOptions}>
          <Checkbox
            checked={value.selectedAgents.length > 0}
            indeterminate={
              value.selectedAgents.length > 0 &&
              value.selectedAgents.length < agents.length
            }
            onChange={(e) => {
              set({
                selectedAgents: e.target.checked ? agents.map((a) => a.id) : [],
              });
            }}
          >
            {"智能体工作区"}
          </Checkbox>

          {value.selectedAgents.length > 0 && (
            <div className={styles.agentSelect}>
              <AgentMultiSelect
                agents={agents}
                value={value.selectedAgents}
                onChange={(ids) => set({ selectedAgents: ids })}
              />
            </div>
          )}

          <Checkbox
            checked={value.globalConfig}
            onChange={(e) => set({ globalConfig: e.target.checked })}
          >
            {"全局设置"}
          </Checkbox>

          <Checkbox
            checked={value.includeGlobalSkills}
            onChange={(e) => set({ includeGlobalSkills: e.target.checked })}
          >
            {"全局技能"}
          </Checkbox>

          <div>
            <Checkbox
              checked={value.includeSecrets}
              onChange={(e) => set({ includeSecrets: e.target.checked })}
            >
              {"密钥信息"}
            </Checkbox>
            <div className={styles.secretsHint}>
              {"包含模型供应商密钥（API Key）和环境变量等敏感信息"}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
