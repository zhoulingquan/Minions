import { Card, Select, Alert } from "antd";
import type { TranscriptionProvider } from "../useVoiceTranscription";
import styles from "../index.module.less";

interface ProviderSelectCardProps {
  availableProviders: TranscriptionProvider[];
  selectedProviderId: string;
  onProviderChange: (id: string) => void;
}

export function ProviderSelectCard({
  availableProviders,
  selectedProviderId,
  onProviderChange,
}: ProviderSelectCardProps) {

  return (
    <Card className={styles.card}>
      <h3 className={styles.cardTitle}>
        {"Whisper API 提供商"}
      </h3>
      <p className={styles.cardDescription}>
        {"选择用于 Whisper API 音频转写的提供商。仅显示支持 Whisper 端点的提供商。"}
      </p>

      {availableProviders.length === 0 ? (
        <Alert
          type="warning"
          showIcon
          message={"未找到支持转写的提供商。请配置一个 OpenAI 提供商以启用语音转写。"}
        />
      ) : (
        <Select
          value={selectedProviderId || undefined}
          onChange={onProviderChange}
          placeholder={"选择提供商..."}
          style={{ width: "100%", maxWidth: 400 }}
        >
          {availableProviders.map((p) => (
            <Select.Option key={p.id} value={p.id}>
              {p.name}
            </Select.Option>
          ))}
        </Select>
      )}
    </Card>
  );
}
