import { Form, Switch, Button, Card, Select } from "@agentscope-ai/design";
import { PlusCircleOutlined } from "@ant-design/icons";
import type { MergedRule } from "../useToolGuard";
import type { ToolGuardConfig } from "../../../../api/modules/security";
import type { FormInstance } from "antd";
import { RuleTable, ShellEvasionSection } from "./index";
import styles from "../index.module.less";

interface ToolGuardTabProps {
  form: FormInstance;
  config: ToolGuardConfig | null;
  enabled: boolean;
  setEnabled: (val: boolean) => void;
  toolOptions: { label: string; value: string }[];
  mergedRules: MergedRule[];
  toggleRule: (ruleId: string, currentlyDisabled: boolean) => void;
  toggleAutoDeny: (ruleId: string, currentlyAutoDeny: boolean) => void;
  onPreviewRule: (rule: MergedRule) => void;
  onEditRule: (rule: MergedRule) => void;
  onDeleteRule: (ruleId: string) => void;
  openAddRule: () => void;
  shellEvasionChecks: Record<string, boolean>;
  toggleShellEvasionCheck: (checkName: string, checked: boolean) => void;
}

export function ToolGuardTab({
  form,
  config,
  enabled,
  setEnabled,
  toolOptions,
  mergedRules,
  toggleRule,
  toggleAutoDeny,
  onPreviewRule,
  onEditRule,
  onDeleteRule,
  openAddRule,
  shellEvasionChecks,
  toggleShellEvasionCheck,
}: ToolGuardTabProps) {

  return (
    <div className={styles.tabContent}>
      <div className={styles.sectionConfigureContainer}>
        <p className={styles.tabDescription}>
          {"配置工具调用的安全扫描。危险操作将在执行前需要你的明确批准。"}
        </p>

        <Card className={styles.formCard}>
          <Form
            form={form}
            layout="vertical"
            className={styles.form}
            initialValues={{
              enabled: config?.enabled ?? true,
              guarded_tools: config?.guarded_tools ?? [],
              denied_tools: config?.denied_tools ?? [],
            }}
          >
            <Form.Item
              label={"启用工具防护"}
              name="enabled"
              valuePropName="checked"
              tooltip={"启用后，工具调用在执行前会被扫描是否包含危险模式"}
            >
              <Switch onChange={(val) => setEnabled(val)} />
            </Form.Item>
            <div className={styles.toolGuardRow}>
              <Form.Item
                label={"受保护的工具"}
                name="guarded_tools"
                tooltip={"检测到危险模式时需要审批的工具。留空则使用内置默认集合。"}
                style={{ marginBottom: 0 }}
              >
                <Select
                  mode="tags"
                  options={toolOptions}
                  placeholder={"选择工具或输入自定义工具名"}
                  disabled={!enabled}
                  allowClear
                  style={{ width: "100%" }}
                />
              </Form.Item>

              <Form.Item
                label={"禁止的工具"}
                name="denied_tools"
                tooltip={"始终被拒绝的工具，无需审批直接拦截"}
                style={{ marginBottom: 0 }}
              >
                <Select
                  mode="tags"
                  options={toolOptions}
                  placeholder={"选择要始终禁止的工具"}
                  disabled={!enabled}
                  allowClear
                  style={{ width: "100%" }}
                />
              </Form.Item>
            </div>
          </Form>
        </Card>
      </div>

      <div className={styles.sectionContainer}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>{"检测规则"}</h2>
          <Button
            type="primary"
            icon={<PlusCircleOutlined />}
            onClick={openAddRule}
            disabled={!enabled}
            size="middle"
          >
            {"添加规则"}
          </Button>
        </div>

        <Card className={styles.tableCard}>
          <RuleTable
            rules={mergedRules}
            enabled={enabled}
            onToggleRule={toggleRule}
            onToggleAutoDeny={toggleAutoDeny}
            onPreviewRule={onPreviewRule}
            onEditRule={onEditRule}
            onDeleteRule={onDeleteRule}
          />
        </Card>
      </div>

      <div className={styles.sectionContainer}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>
            {"Shell 逃逸检测"}
          </h2>
        </div>
        <div className={styles.sectionConfigureContainer}>
          <p className={styles.tabDescription}>
            {"配置启用哪些 Shell 逃逸和混淆检测。这些检测能够发现试图绕过简单正则检测来隐藏恶意意图的技术手段。"}
          </p>
          <ShellEvasionSection
            checks={shellEvasionChecks}
            onToggle={toggleShellEvasionCheck}
            disabled={!enabled}
          />
        </div>
      </div>
    </div>
  );
}
