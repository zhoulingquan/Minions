import { Card, Radio, Space, Alert } from "antd";
import type { LocalWhisperStatus } from "../useVoiceTranscription";
import styles from "../index.module.less";

interface AudioModeCardProps {
  audioMode: string;
  onAudioModeChange: (value: string) => void;
  localWhisperStatus: LocalWhisperStatus | null;
}

export function AudioModeCard({
  audioMode,
  onAudioModeChange,
  localWhisperStatus,
}: AudioModeCardProps) {

  return (
    <Card className={styles.card}>
      <h3 className={styles.cardTitle}>
        {"音频模式"}
      </h3>
      <p className={styles.cardDescription}>
        {"选择来自频道（Discord、Telegram 等）的语音消息在发送给模型之前如何处理。"}
      </p>
      <Radio.Group
        value={audioMode}
        onChange={(e) => onAudioModeChange(e.target.value)}
      >
        <Space direction="vertical" size="middle">
          <Radio value="auto">
            <span className={styles.optionLabel}>
              {"自动（推荐）"}
            </span>
            <span className={styles.optionDescription}>
              {"使用所选转写提供商将音频转写为文字后发送给模型。如果转写未启用或不可用，则显示文件上传占位消息。此模式下音频不会直接发送给模型。适用于所有模型。"}
            </span>
          </Radio>
          <Radio value="native">
            <span className={styles.optionLabel}>
              {"原生音频"}
            </span>
            <span className={styles.optionDescription}>
              {"直接将音频文件发送给模型，不进行转写。这是唯一会将音频发送给模型的模式。仅适用于特定的音频模型（如 gpt-4o-audio），大多数模型不支持此模式。"}
            </span>
          </Radio>
        </Space>
      </Radio.Group>

      {audioMode === "native" && localWhisperStatus && (
        <div style={{ marginTop: 12 }}>
          {localWhisperStatus.ffmpeg_installed ? (
            <Alert
              type="success"
              showIcon
              message={"ffmpeg 已安装。原生模式音频格式转换可用。"}
            />
          ) : (
            <Alert
              type="warning"
              showIcon
              message={"ffmpeg 未安装。"}
              description={"原生音频模式需要 ffmpeg 来转换音频格式（如 .ogg 转 .wav）。请安装 ffmpeg 系统包以启用此模式。"}
            />
          )}
        </div>
      )}
    </Card>
  );
}
