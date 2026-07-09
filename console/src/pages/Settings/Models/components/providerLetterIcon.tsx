const PROVIDER_LETTER_COLORS: Record<string, string> = {
  deepseek: "#4D6BFE",
  "minions-local": "#FF7F16",
  ollama: "#1A1A1A",
  lmstudio: "#6C5CE7",
};

const FALLBACK_COLORS = [
  "#FF6B6B",
  "#4ECDC4",
  "#45B7D1",
  "#96CEB4",
  "#FFEAA7",
  "#DDA0DD",
  "#98D8C8",
  "#F7DC6F",
  "#BB8FCE",
  "#85C1E9",
  "#F0B27A",
  "#82E0AA",
];

export function getProviderLetterColor(providerId: string): string {
  if (PROVIDER_LETTER_COLORS[providerId]) {
    return PROVIDER_LETTER_COLORS[providerId];
  }
  let hash = 0;
  for (let i = 0; i < providerId.length; i++) {
    hash = ((hash << 5) - hash + providerId.charCodeAt(i)) | 0;
  }
  return FALLBACK_COLORS[Math.abs(hash) % FALLBACK_COLORS.length];
}

export function getProviderLetter(providerId: string): string {
  return providerId.charAt(0).toUpperCase();
}
