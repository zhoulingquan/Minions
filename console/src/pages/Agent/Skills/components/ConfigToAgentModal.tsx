import { useEffect, useMemo, useState } from "react";
import { Button, Modal, Tooltip } from "@agentscope-ai/design";
import { CheckOutlined } from "@ant-design/icons";
import type {
  GlobalSkillSpec,
  WorkspaceSkillSummary,
} from "../../../../api/types";
import { getAgentDisplayName } from "@/utils/agentDisplayName";
import { useSkillFilter } from "../useSkillFilter";
import styles from "../index.module.less";

interface ConfigToAgentModalProps {
  open: boolean;
  skills: GlobalSkillSpec[];
  workspaces: WorkspaceSkillSummary[];
  initialSkillNames: string[];
  onCancel: () => void;
  onConfirm: (skillNames: string[], workspaceIds: string[]) => Promise<void>;
}

export function ConfigToAgentModal({
  open,
  skills,
  workspaces,
  initialSkillNames,
  onCancel,
  onConfirm,
}: ConfigToAgentModalProps) {
    const [selectedSkillNames, setSelectedSkillNames] =
    useState<string[]>(initialSkillNames);
  const [selectedWorkspaceIds, setSelectedWorkspaceIds] = useState<string[]>(
    [],
  );
  const { filteredSkills } = useSkillFilter(skills);

  const builtinSkillNames = useMemo(
    () => skills.filter((s) => s.source === "builtin").map((s) => s.name),
    [skills],
  );

  useEffect(() => {
    if (open) {
      setSelectedSkillNames(initialSkillNames);
      setSelectedWorkspaceIds([]);
    }
  }, [open, initialSkillNames]);

  const handleCancel = () => {
    setSelectedSkillNames([]);
    setSelectedWorkspaceIds([]);
    onCancel();
  };

  return (
    <Modal
      open={open}
      onCancel={handleCancel}
      onOk={() => onConfirm(selectedSkillNames, selectedWorkspaceIds)}
      okButtonProps={{
        disabled:
          selectedSkillNames.length === 0 || selectedWorkspaceIds.length === 0,
      }}
      title={"配置到智能体"}
      width={640}
    >
      <div style={{ display: "grid", gap: 12 }}>
        <div className={styles.pickerSection}>
          <div className={styles.pickerHeader}>
            <div className={styles.pickerLabel}>
              {"选择想要配置到智能体的技能"}
            </div>
            <div className={styles.bulkActions}>
              <Button
                size="small"
                type="primary"
                onClick={() =>
                  setSelectedSkillNames(filteredSkills.map((s) => s.name))
                }
              >
                {"全选"}
              </Button>
              <Button
                size="small"
                onClick={() => setSelectedSkillNames(builtinSkillNames)}
              >
                {"内置"}
              </Button>
              <Button size="small" onClick={() => setSelectedSkillNames([])}>
                {"清除"}
              </Button>
            </div>
          </div>
        </div>

        <div className={`${styles.pickerGrid} ${styles.compactPickerGrid}`}>
          {filteredSkills.map((skill) => {
            const selected = selectedSkillNames.includes(skill.name);
            return (
              <div
                key={skill.name}
                className={`${styles.pickerCard} ${styles.compactPickerCard} ${
                  selected ? styles.pickerCardSelected : ""
                }`}
                onClick={() =>
                  setSelectedSkillNames(
                    selected
                      ? selectedSkillNames.filter((n) => n !== skill.name)
                      : [...selectedSkillNames, skill.name],
                  )
                }
              >
                {selected && (
                  <span
                    className={`${styles.pickerCheck} ${styles.compactPickerCheck}`}
                  >
                    <CheckOutlined />
                  </span>
                )}
                <Tooltip title={skill.name}>
                  <div
                    className={`${styles.pickerCardTitle} ${styles.compactPickerTitle}`}
                  >
                    {skill.name}
                  </div>
                </Tooltip>
              </div>
            );
          })}
        </div>
        <div className={styles.pickerSection}>
          <div className={styles.pickerHeader}>
            <div className={styles.pickerLabel}>
              {"选择要配置的智能体"}
            </div>
            <div className={styles.bulkActions}>
              <Button
                size="small"
                type="primary"
                onClick={() =>
                  setSelectedWorkspaceIds(workspaces.map((ws) => ws.agent_id))
                }
              >
                {"所有智能体"}
              </Button>
              <Button size="small" onClick={() => setSelectedWorkspaceIds([])}>
                {"清除"}
              </Button>
            </div>
          </div>
        </div>

        <div className={`${styles.pickerGrid} ${styles.compactPickerGrid}`}>
          {workspaces.map((workspace) => {
            const selected = selectedWorkspaceIds.includes(workspace.agent_id);
            return (
              <div
                key={workspace.agent_id}
                className={`${styles.pickerCard} ${styles.compactPickerCard} ${
                  selected ? styles.pickerCardSelected : ""
                }`}
                onClick={() =>
                  setSelectedWorkspaceIds(
                    selected
                      ? selectedWorkspaceIds.filter(
                          (id) => id !== workspace.agent_id,
                        )
                      : [...selectedWorkspaceIds, workspace.agent_id],
                  )
                }
              >
                {selected && (
                  <span
                    className={`${styles.pickerCheck} ${styles.compactPickerCheck}`}
                  >
                    <CheckOutlined />
                  </span>
                )}
                <Tooltip title={`ID: ${workspace.agent_id}`}>
                  <div
                    className={`${styles.pickerCardTitle} ${styles.compactPickerTitle}`}
                  >
                    {getAgentDisplayName(
                      {
                        id: workspace.agent_id,
                        name: workspace.agent_name ?? "",
                      },
                    )}
                  </div>
                </Tooltip>
              </div>
            );
          })}
        </div>
      </div>
    </Modal>
  );
}
