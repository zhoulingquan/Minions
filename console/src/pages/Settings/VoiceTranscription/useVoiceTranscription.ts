import { useCallback, useEffect, useState } from "react";
import api from "../../../api";
import { useAppMessage } from "../../../hooks/useAppMessage";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface TranscriptionProvider {
  id: string;
  name: string;
  available: boolean;
}

export interface LocalWhisperStatus {
  available: boolean;
  ffmpeg_installed: boolean;
  whisper_installed: boolean;
}

// ─── Hook ───────────────────────────────────────────────────────────────────

export function useVoiceTranscription() {
    const { message } = useAppMessage();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [audioMode, setAudioMode] = useState("auto");
  const [providerType, setProviderType] = useState("disabled");
  const [providers, setProviders] = useState<TranscriptionProvider[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [localWhisperStatus, setLocalWhisperStatus] =
    useState<LocalWhisperStatus | null>(null);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const [modeRes, provTypeRes, provRes, lwStatus] = await Promise.all([
        api.getAudioMode(),
        api.getTranscriptionProviderType(),
        api.getTranscriptionProviders(),
        api.getLocalWhisperStatus(),
      ]);
      setAudioMode(modeRes.audio_mode ?? "auto");
      setProviderType(provTypeRes.transcription_provider_type ?? "disabled");
      setProviders(provRes.providers ?? []);
      setSelectedProviderId(provRes.configured_provider_id ?? "");
      setLocalWhisperStatus(lwStatus);
    } catch (err) {
      console.error("Failed to load voice transcription settings:", err);
      message.error("加载音频模式设置失败");
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    void fetchSettings();
  }, [fetchSettings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const promises: Promise<unknown>[] = [
        api.updateAudioMode(audioMode),
        api.updateTranscriptionProviderType(providerType),
      ];
      if (providerType === "whisper_api") {
        promises.push(api.updateTranscriptionProvider(selectedProviderId));
      }
      await Promise.all(promises);
      message.success("音频模式已保存");
    } catch (err) {
      console.error("Failed to save voice transcription settings:", err);
      message.error("保存音频模式失败");
    } finally {
      setSaving(false);
    }
  };

  // Derived state
  const availableProviders = providers.filter((p) => p.available);
  const showProviderSection = audioMode !== "native";
  const isLocalWhisper = providerType === "local_whisper";
  const isWhisperApi = providerType === "whisper_api";

  return {
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
  };
}
