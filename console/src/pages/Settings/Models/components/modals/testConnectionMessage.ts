import type { TestConnectionResponse } from "../../../../../api/types";

const FAILURE_PREFIX_PATTERNS = [
  /^Connection failed:\s*/i,
  /^Model connection failed:\s*/i,
];

const GENERIC_FAILURE_MESSAGES = new Set([
  "connection failed",
  "model connection failed",
]);

function normalizeFailureMessage(message: string): string {
  return message.toLowerCase().trim().replace(/\.+$/, "");
}

function isGenericFailureMessage(message: string): boolean {
  return GENERIC_FAILURE_MESSAGES.has(normalizeFailureMessage(message));
}

export function getTestConnectionFailureDetail(
  message?: string | null,
): string | null {
  const trimmed = message?.trim();
  if (!trimmed || isGenericFailureMessage(trimmed)) {
    return null;
  }

  for (const pattern of FAILURE_PREFIX_PATTERNS) {
    if (pattern.test(trimmed)) {
      const detail = trimmed.replace(pattern, "").trim();
      return detail && !isGenericFailureMessage(detail) ? detail : null;
    }
  }

  return trimmed;
}

export function getLocalizedTestConnectionMessage(
  result: Pick<TestConnectionResponse, "success" | "message">,
): string {
  if (result.success) {
    return "连接测试成功";
  }

  const detail = getTestConnectionFailureDetail(result.message);
  return detail
    ? `连接测试失败：${detail}`
    : "连接测试失败";
}
