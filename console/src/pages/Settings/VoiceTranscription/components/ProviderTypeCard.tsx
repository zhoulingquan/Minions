import { Card, Radio, Space, Alert } from "antd";
import type { LocalWhisperStatus } from "../useVoiceTranscription";
import styles from "../index.module.less";

interface ProviderTypeCardProps {
  providerType: string;
  onProviderTypeChange: (value: string) => void;
  isLocalWhisper: boolean;
  localWhisperStatus: LocalWhisperStatus | null;
}

export function ProviderTypeCard({
  providerType,
  onProviderTypeChange,
  isLocalWhisper,
  localWhisperStatus,
}: ProviderTypeCardProps) {

  return (
    <Card className={styles.card}>
      <h3 className={styles.cardTitle}>
        {"转写提供商"}
      </h3>
      <p className={styles.cardDescription}>
        {"选择转写后端。如果不需要语音转写，请选择「已禁用」。"}
      </p>
      <Radio.Group
        value={providerType}
        onChange={(e) => onProviderTypeChange(e.target.value)}
      >
        <Space direction="vertical" size="middle">
          <Radio value="disabled">
            <span className={styles.optionLabel}>
              {"已禁用"}
            </span>
            <span className={styles.optionDescription}>
              {"不进行转写。语音消息将显示为文件上传占位消息。"}
            </span>
          </Radio>
          <Radio value="whisper_api">
            <span className={styles.optionLabel}>
              {"Whisper API"}
            </span>
            <span className={styles.optionDescription}>
              {"使用已配置提供商（如 OpenAI、Ollama）的 OpenAI 兼容 Whisper API 端点。"}
            </span>
          </Radio>
          <Radio value="local_whisper">
            <span className={styles.optionLabel}>
              {"本地 Whisper"}
            </span>
            <span className={styles.optionDescription}>
              {"使用本地安装的 openai-whisper Python 库进行转写。需要同时安装 ffmpeg 和 openai-whisper。"}
            </span>
          </Radio>
        </Space>
      </Radio.Group>

      {isLocalWhisper && localWhisperStatus && (
        <div style={{ marginTop: 12 }}>
          {localWhisperStatus.available ? (
            <Alert
              type="success"
              showIcon
              message={"本地 Whisper 已就绪。ffmpeg 和 openai-whisper 均已安装。"}
            />
          ) : (
            <Alert
              type="warning"
              showIcon
              message={"本地 Whisper 未就绪，缺少必要依赖。"}
              description={`ffmpeg: ${
                localWhisperStatus.ffmpeg_installed ? "已启用" : "已禁用"
              } | openai-whisper: ${
                localWhisperStatus.whisper_installed ? "已启用" : "已禁用"
              }。请安装缺少的依赖：ffmpeg（系统包）和 openai-whisper（uv pip install openai-whisper，或使用 [whisper] 额外依赖安装 Minions）。`}
            />
          )}
        </div>
      )}
    </Card>
  );
}
