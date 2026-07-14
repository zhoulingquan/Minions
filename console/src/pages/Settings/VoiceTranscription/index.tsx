import { Button } from "@agentscope-ai/design";
import { Alert, Spin } from "antd";
import { PageHeader } from "@/components/PageHeader";
import { useVoiceTranscription } from "./useVoiceTranscription";
import {
  AudioModeCard,
  ProviderTypeCard,
  ProviderSelectCard,
} from "./components";
import styles from "./index.module.less";

function VoiceTranscriptionPage() {
    const {
    loading,
    saving,
    audioMode,
    setAudioMode,
    providerType,
    setProviderType,
    selectedProviderId,
    setSelectedProviderId,
    localWhisperStatus,
    availableProviders,
    showProviderSection,
    isLocalWhisper,
    isWhisperApi,
    fetchSettings,
    handleSave,
  } = useVoiceTranscription();

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.centerState}>
          <Spin />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.voiceTranscriptionPage}>
      <PageHeader
        items={[
          { title: "设置" },
          { title: "语音转写" },
        ]}
      />
      <Alert
        type="info"
        showIcon
        message={"转写工作原理"}
        description={
          isLocalWhisper
            ? "本地 Whisper 转写直接在您的设备上运行 openai-whisper 库。需要同时安装 ffmpeg（用于音频解码）和 openai-whisper Python 包。无需 API Key 或网络连接。安装命令：uv pip install 'minions[whisper]'。"
            : "Whisper API 转写使用 OpenAI 兼容的 /v1/audio/transcriptions 端点。需要配置一个支持 Whisper 端点的提供商（如 OpenAI）。请在上方选择具体的提供商以启用转写。"
        }
      />
      <div className={styles.content}>
        <AudioModeCard
          audioMode={audioMode}
          onAudioModeChange={setAudioMode}
          localWhisperStatus={localWhisperStatus}
        />

        {showProviderSection && (
          <>
            <ProviderTypeCard
              providerType={providerType}
              onProviderTypeChange={setProviderType}
              isLocalWhisper={isLocalWhisper}
              localWhisperStatus={localWhisperStatus}
            />

            {isWhisperApi && (
              <ProviderSelectCard
                availableProviders={availableProviders}
                selectedProviderId={selectedProviderId}
                onProviderChange={setSelectedProviderId}
              />
            )}
          </>
        )}
      </div>

      <div className={styles.footerButtons}>
        <Button
          onClick={fetchSettings}
          disabled={saving}
          style={{ marginRight: 8 }}
        >
          {"重置"}
        </Button>
        <Button type="primary" onClick={handleSave} loading={saving}>
          {"保存"}
        </Button>
      </div>
    </div>
  );
}

export default VoiceTranscriptionPage;
