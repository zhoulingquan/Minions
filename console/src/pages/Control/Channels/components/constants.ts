// Channel key type - now accepts any string for custom channels
export type ChannelKey = string;

// Built-in channel labels
export const CHANNEL_LABELS: Record<string, string> = {
  imessage: "iMessage",
  discord: "Discord",
  dingtalk: "DingTalk",
  feishu: "Feishu",
  qq: "QQ",
  telegram: "Telegram",
  slack: "Slack",
  mqtt: "MQTT",
  mattermost: "Mattermost",
  matrix: "Matrix",
  console: "Console",
  voice: "Twilio",
  sip: "SIP",
  wecom: "WeCom",
  xiaoyi: "XiaoYi",
  wechat: "WeChat",
  onebot: "OneBot",
  yuanbao: "Yuanbao",
};

function formatCustomChannelKey(key: string): string {
  return key
    .split(/[_-]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// Per-locale strings under `channels.channelNames.*`; missing keys use `defaultValue` (English labels).
export function getChannelLabel(key: string): string {
  return CHANNEL_LABELS[key] ?? formatCustomChannelKey(key);
}
