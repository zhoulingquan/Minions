import React from "react";
import { PlusOutlined } from "@ant-design/icons";
import { Button } from "@agentscope-ai/design";
import type {
  MCPAccessEffect,
  MCPAccessPolicy,
  MCPAccessPrincipalOption,
  MCPAccessRule,
} from "../../../../api/types";
import { accessRuleIdentityKey } from "../accessPolicy";
import styles from "../index.module.less";
import { MCPAccessPolicySegmented } from "./MCPAccessPolicySegmented";
import { MCPAccessRuleRows } from "./MCPAccessRuleRows";

interface MCPAccessClientPanelProps {
  policy: MCPAccessPolicy;
  principalOptions: MCPAccessPrincipalOption[];
  setDefaultEffect: (effect: MCPAccessEffect) => void;
  addClientAccessRule: () => void;
  updateClientRule: (
    rule: MCPAccessRule,
    patch: Partial<MCPAccessRule>,
  ) => void;
  setClientRuleEffect: (rule: MCPAccessRule, effect: MCPAccessEffect) => void;
  deleteClientRule: (rule: MCPAccessRule) => void;
  effectLabel: (effect: MCPAccessEffect) => string;
}

export const MCPAccessClientPanel: React.FC<MCPAccessClientPanelProps> = ({
  policy,
  principalOptions,
  setDefaultEffect,
  addClientAccessRule,
  updateClientRule,
  setClientRuleEffect,
  deleteClientRule,
  effectLabel,
}) => {

  return (
    <div className={styles.accessClientPanel}>
      <div className={styles.accessClientControlRow}>
        <div
          className={`${styles.accessSectionTitle} ${styles.accessClientTitle}`}
        >
          {"整体权限"}
        </div>
        <div className={styles.accessDefaultRow}>
          <span className={styles.accessDefaultLabel}>
            {"默认策略"}
          </span>
          <MCPAccessPolicySegmented
            value={policy.default_effect}
            onChange={setDefaultEffect}
            effectLabel={effectLabel}
          />
        </div>
        <Button
          className={styles.accessClientAddButton}
          icon={<PlusOutlined />}
          onClick={addClientAccessRule}
        >
          {"新增规则"}
        </Button>
      </div>
      <MCPAccessRuleRows
        rules={policy.client_overrides}
        principalOptions={principalOptions}
        getKey={accessRuleIdentityKey}
        updateRule={updateClientRule}
        setRuleEffect={setClientRuleEffect}
        deleteRule={deleteClientRule}
        emptyText={"暂无规则"}
        effectLabel={effectLabel}
      />
    </div>
  );
};
