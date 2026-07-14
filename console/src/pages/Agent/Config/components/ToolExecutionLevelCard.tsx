import { Card, Radio, Alert, Space, Typography } from "antd";
import { Shield, CheckCircle, AlertTriangle, Ban } from "lucide-react";
import styles from "../index.module.less";

const { Text, Paragraph } = Typography;

export type ToolExecutionLevel = "STRICT" | "SMART" | "AUTO" | "OFF";

interface LevelOption {
  value: ToolExecutionLevel;
  label: string;
  icon: React.ReactNode;
  description: string;
  color: string;
}

interface ToolExecutionLevelCardProps {
  value: ToolExecutionLevel;
  onChange: (level: ToolExecutionLevel) => void;
  disabled?: boolean;
}

export function ToolExecutionLevelCard({
  value: level,
  onChange,
  disabled = false,
}: ToolExecutionLevelCardProps) {
  const levelOptions: LevelOption[] = [
    {
      value: "STRICT",
      label: "严格模式",
      icon: <Ban size={18} />,
      description: "所有工具调用都需要审批，最高安全级别",
      color: "#ff4d4f",
    },
    {
      value: "SMART",
      label: "智能模式",
      icon: <AlertTriangle size={18} />,
      description: "低风险工具自动放行，中高风险工具需要审批",
      color: "#faad14",
    },
    {
      value: "AUTO",
      label: "自动模式",
      icon: <Shield size={18} />,
      description: "仅被明确标记为需要审批的工具才会要求审批（默认）",
      color: "#1890ff",
    },
    {
      value: "OFF",
      label: "关闭模式",
      icon: <CheckCircle size={18} />,
      description: "关闭所有工具审批，所有工具自动执行",
      color: "#52c41a",
    },
  ];

  return (
    <Card
      className={styles.formCard}
      title={
        <Space>
          <Shield size={18} />
          {"工具执行安全"}
        </Space>
      }
    >
      <Alert
        type="info"
        message={"配置工具调用的审批策略，控制智能体执行工具时的安全级别"}
        style={{ marginBottom: 24 }}
        showIcon
      />

      <Radio.Group
        value={level}
        onChange={(e) => onChange(e.target.value as ToolExecutionLevel)}
        disabled={disabled}
        style={{ width: "100%" }}
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          {levelOptions.map((option) => (
            <Card
              key={option.value}
              className={styles.levelOptionCard}
              style={{
                borderColor: level === option.value ? option.color : undefined,
                borderWidth: level === option.value ? 2 : 1,
                cursor: "pointer",
                transition: "all 0.3s",
              }}
              onClick={() => !disabled && onChange(option.value)}
              hoverable
            >
              <Radio value={option.value} style={{ width: "100%" }}>
                <div style={{ marginLeft: 12 }}>
                  <Space align="start" size={12}>
                    <div style={{ color: option.color, marginTop: 2 }}>
                      {option.icon}
                    </div>
                    <div style={{ flex: 1 }}>
                      <Text strong style={{ fontSize: 15 }}>
                        {option.label}
                      </Text>
                      <Paragraph
                        type="secondary"
                        style={{ margin: "4px 0 0 0", fontSize: 13 }}
                      >
                        {option.description}
                      </Paragraph>
                    </div>
                  </Space>
                </div>
              </Radio>
            </Card>
          ))}
        </Space>
      </Radio.Group>
    </Card>
  );
}
