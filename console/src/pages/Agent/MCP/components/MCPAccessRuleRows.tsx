import React, { useEffect, useState } from "react";
import { DeleteOutlined } from "@ant-design/icons";
import { Button, Input, Select } from "@agentscope-ai/design";
import { AutoComplete } from "antd";
import type {
  MCPAccessEffect,
  MCPAccessPrincipalOption,
  MCPAccessRule,
  MCPAccessSourceType,
  MCPAccessSubjectType,
} from "../../../../api/types";
import {
  buildSubjectValueOptions,
  MCP_CHANNEL_SOURCE_VALUES,
  ruleHasAmbiguousUserSource,
  ruleHasUnknownUserValue,
} from "../accessPolicy";
import styles from "../index.module.less";

interface RuleTextInputProps {
  value: string;
  placeholder: string;
  className: string;
  onCommit: (value: string) => void;
}

const RuleTextInput: React.FC<RuleTextInputProps> = ({
  value,
  placeholder,
  className,
  onCommit,
}) => {
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  return (
    <Input
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => onCommit(draft)}
      onPressEnter={() => onCommit(draft)}
      placeholder={placeholder}
      className={className}
    />
  );
};

interface RuleSubjectValueInputProps {
  value: string;
  placeholder: string;
  noOptionsText: string;
  options: { label: string; value: string }[];
  className: string;
  onCommit: (value: string) => void;
}

const RuleSubjectValueInput: React.FC<RuleSubjectValueInputProps> = ({
  value,
  placeholder,
  noOptionsText,
  options,
  className,
  onCommit,
}) => {
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  const commit = (nextValue: string) => {
    const trimmed = nextValue.trim();
    setDraft(trimmed);
    onCommit(trimmed);
  };

  return (
    <AutoComplete
      value={draft}
      options={options}
      className={className}
      placeholder={options.length > 0 ? placeholder : noOptionsText}
      notFoundContent={noOptionsText}
      onChange={(nextValue) => setDraft(String(nextValue))}
      onSelect={(nextValue) => commit(String(nextValue))}
      onBlur={() => commit(draft)}
      filterOption={(inputValue, option) =>
        String(option?.value || "")
          .toLowerCase()
          .includes(inputValue.toLowerCase())
      }
    >
      <Input onPressEnter={() => commit(draft)} />
    </AutoComplete>
  );
};

const CHANNEL_SOURCE_FALLBACK_LABELS: Record<string, string> = {
  console: "Console",
  dingtalk: "DingTalk",
  feishu: "Feishu",
  wechat: "WeChat",
  wecom: "WeCom",
  discord: "Discord",
  telegram: "Telegram",
  qq: "QQ",
  imessage: "iMessage",
  mattermost: "Mattermost",
  matrix: "Matrix",
  onebot: "OneBot",
  mqtt: "MQTT",
  voice: "Voice",
  sip: "SIP",
  xiaoyi: "XiaoYi",
};

function channelSourceOptions(
  allChannelsLabel: string,
  channelLabel: (value: string) => string,
): { label: string; value: string }[] {
  return [
    {
      label: allChannelsLabel,
      value: "*",
    },
    ...MCP_CHANNEL_SOURCE_VALUES.map((value) => ({
      label: channelLabel(value),
      value,
    })),
  ];
}

function sourceTypeOptions(
  currentSourceType: string,
  channelLabel: string,
): { label: string; value: string }[] {
  const options = [
    {
      label: channelLabel,
      value: "channel",
    },
  ];
  if (currentSourceType && currentSourceType !== "channel") {
    options.push({
      label: currentSourceType,
      value: currentSourceType,
    });
  }
  return options;
}

function sourceValueSelectValue(sourceValue: string): string {
  return sourceValue || "*";
}

interface MCPAccessRuleRowsProps<Rule extends MCPAccessRule> {
  rules: Rule[];
  principalOptions?: MCPAccessPrincipalOption[];
  getKey: (rule: Rule) => string;
  updateRule: (rule: Rule, patch: Partial<MCPAccessRule>) => void;
  setRuleEffect: (rule: Rule, effect: MCPAccessEffect) => void;
  deleteRule: (rule: Rule) => void;
  emptyText: string;
  effectLabel: (effect: MCPAccessEffect) => string;
}

export function MCPAccessRuleRows<Rule extends MCPAccessRule>({
  rules,
  principalOptions = [],
  getKey,
  updateRule,
  setRuleEffect,
  deleteRule,
  emptyText,
  effectLabel,
}: MCPAccessRuleRowsProps<Rule>) {
    const channelLabel = (value: string) =>
    CHANNEL_SOURCE_FALLBACK_LABELS[value] || value;
  const sourceValueOptions = channelSourceOptions(
    "所有频道",
    channelLabel,
  );
  const channelSourceTypeLabel = "频道";
  const subjectTypeOptions = [
    { label: "全部", value: "all" },
    { label: "用户", value: "user" },
  ];
  if (rules.length === 0) {
    return <div className={styles.accessNoRules}>{emptyText}</div>;
  }

  return (
    <div className={styles.accessRuleList}>
      {rules.map((rule) => (
        <AccessRuleRow
          key={getKey(rule)}
          rule={rule}
          principalOptions={principalOptions}
          sourceValueOptions={sourceValueOptions}
          channelSourceTypeLabel={channelSourceTypeLabel}
          subjectTypeOptions={subjectTypeOptions}
          updateRule={updateRule}
          setRuleEffect={setRuleEffect}
          deleteRule={deleteRule}
          effectLabel={effectLabel}
        />
      ))}
    </div>
  );
}

interface AccessRuleRowProps<Rule extends MCPAccessRule> {
  rule: Rule;
  principalOptions: MCPAccessPrincipalOption[];
  sourceValueOptions: { label: string; value: string }[];
  channelSourceTypeLabel: string;
  subjectTypeOptions: { label: string; value: string }[];
  updateRule: (rule: Rule, patch: Partial<MCPAccessRule>) => void;
  setRuleEffect: (rule: Rule, effect: MCPAccessEffect) => void;
  deleteRule: (rule: Rule) => void;
  effectLabel: (effect: MCPAccessEffect) => string;
}

function AccessRuleRow<Rule extends MCPAccessRule>({
  rule,
  principalOptions,
  sourceValueOptions,
  channelSourceTypeLabel,
  subjectTypeOptions,
  updateRule,
  setRuleEffect,
  deleteRule,
  effectLabel,
}: AccessRuleRowProps<Rule>) {
    const subjectValueOptions = buildSubjectValueOptions(principalOptions, rule);
  const hasUnknownUserValue = ruleHasUnknownUserValue(principalOptions, rule);

  return (
    <div className={styles.accessRuleRow}>
      <div className={styles.accessRuleField}>
        <span className={styles.accessRuleFieldLabel}>
          {"调用来源"}
        </span>
        <Select
          className={styles.accessRuleSourceType}
          value={rule.source_type || "channel"}
          onChange={(sourceType) =>
            updateRule(rule, {
              source_type: String(sourceType) as MCPAccessSourceType,
              source_value:
                String(sourceType) === "channel"
                  ? sourceValueSelectValue(rule.source_value)
                  : rule.source_value,
            })
          }
          options={sourceTypeOptions(rule.source_type, channelSourceTypeLabel)}
        />
      </div>
      <div className={styles.accessRuleField}>
        <span className={styles.accessRuleFieldLabel}>
          {"来源值"}
        </span>
        {rule.source_type === "channel" ? (
          <Select
            className={styles.accessRuleSourceValue}
            value={sourceValueSelectValue(rule.source_value)}
            onChange={(sourceValue) =>
              updateRule(rule, {
                source_value: String(sourceValue),
              })
            }
            options={sourceValueOptions}
          />
        ) : (
          <RuleTextInput
            value={rule.source_value}
            placeholder={"控制台 / 钉钉"}
            className={styles.accessRuleSourceValue}
            onCommit={(sourceValue) =>
              updateRule(rule, {
                source_value: sourceValue,
              })
            }
          />
        )}
      </div>
      <div className={styles.accessRuleField}>
        <span className={styles.accessRuleFieldLabel}>
          {"对象"}
        </span>
        <Select
          className={styles.accessRuleSubjectType}
          value={rule.subject_type}
          onChange={(value) =>
            updateRule(rule, {
              subject_type: value as MCPAccessSubjectType,
            })
          }
          options={subjectTypeOptions}
        />
      </div>
      <div className={styles.accessRuleField}>
        <span className={styles.accessRuleFieldLabel}>
          {"对象值"}
        </span>
        {rule.subject_type === "user" ? (
          <div className={styles.accessRuleSubjectStack}>
            <RuleSubjectValueInput
              value={rule.subject_value}
              placeholder={"用户 ID 仅在所选来源内有效；请重新输入或选择"}
              noOptionsText={"该来源暂无近期用户，可手动输入用户 ID"}
              options={subjectValueOptions}
              className={styles.accessRuleSubjectValue}
              onCommit={(subjectValue) =>
                updateRule(rule, {
                  subject_value: subjectValue,
                })
              }
            />
            {ruleHasAmbiguousUserSource(rule) && (
              <div className={styles.accessRuleWarning}>
                {"用户 ID 仅在来源内唯一，请选择具体频道以避免跨频道误匹配。"}
              </div>
            )}
            {hasUnknownUserValue && (
              <div className={styles.accessRuleWarning}>
                {"该用户 ID 未出现在近期活跃用户中，但仍可保存。"}
              </div>
            )}
          </div>
        ) : (
          <Input
            className={styles.accessRuleSubjectValue}
            value={"全部"}
            disabled
          />
        )}
      </div>
      <div className={styles.accessRuleField}>
        <span className={styles.accessRuleFieldLabel}>
          {"策略"}
        </span>
        <Select
          className={styles.accessRuleEffect}
          value={rule.effect}
          onChange={(value) => setRuleEffect(rule, value as MCPAccessEffect)}
          options={[
            { label: effectLabel("allow"), value: "allow" },
            { label: effectLabel("ask"), value: "ask" },
            { label: effectLabel("deny"), value: "deny" },
          ]}
        />
      </div>
      <Button
        className={styles.accessRuleDeleteButton}
        icon={<DeleteOutlined />}
        onClick={() => deleteRule(rule)}
        title={"删除规则"}
      />
    </div>
  );
}
